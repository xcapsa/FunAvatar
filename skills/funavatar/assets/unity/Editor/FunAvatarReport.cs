// Copy explicitly into Assets/Editor. Unity 2022.3+; no SDK assembly references.
// Reads the selected hierarchy and existing assets only. Does not save or upload.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace FunAvatar
{
    public static class FunAvatarReport
    {
        [Serializable]
        public sealed class Observations
        {
            public int renderer_count;
            public int missing_scripts;
            public int missing_material_slots;
            public int missing_shaders;
            public int missing_animation_bindings;
            public int checked_animation_bindings;
            public int conditional_animation_bindings;
            public int invalid_humanoid_avatars;
            public int vrchat_descriptor_count;
        }

        [Serializable]
        public sealed class Report
        {
            public int schema_version = 1;
            public string tool = "unity";
            public string tool_version;
            public string subject;
            public Observations observations = new Observations();
        }

        [MenuItem("Tools/FunAvatar/Export selected avatar observations")]
        private static void ExportSelected()
        {
            GameObject root = Selection.activeGameObject;
            if (root == null)
            {
                EditorUtility.DisplayDialog("FunAvatar", "Select the avatar root first.", "OK");
                return;
            }
            string path = EditorUtility.SaveFilePanel("Export new FunAvatar report", "",
                "funavatar-unity-report.json", "json");
            if (string.IsNullOrEmpty(path)) return;
            try
            {
                Export(root, path);
                Debug.Log("FunAvatar observations exported. Review bindings in the build preview; " +
                    "this report does not establish VRChat readiness.");
            }
            catch (Exception error)
            {
                // Avoid writing absolute project or output paths to the report/log.
                EditorUtility.DisplayDialog("FunAvatar export failed", error.GetType().Name +
                    ": select a new writable report filename and a valid avatar root.", "OK");
            }
        }

        [MenuItem("Tools/FunAvatar/Export selected avatar observations", true)]
        private static bool CanExportSelected() { return Selection.activeGameObject != null; }

        public static void Export(GameObject root, string path)
        {
            if (root == null) throw new ArgumentNullException("root");
            if (File.Exists(path)) throw new IOException("Report already exists");
            string json = JsonUtility.ToJson(Collect(root), true);
            using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write))
            using (var writer = new StreamWriter(stream, new UTF8Encoding(false)))
                writer.WriteLine(json);
        }

        public static Report Collect(GameObject root)
        {
            if (root == null) throw new ArgumentNullException("root");
            var report = new Report { tool_version = Application.unityVersion,
                subject = SafeSubject(root.name) };
            Observations facts = report.observations;
            Transform[] hierarchy = root.GetComponentsInChildren<Transform>(true);
            var descriptors = new List<Component>();
            bool hasMergeTool = false;
            foreach (Transform node in hierarchy)
            {
                facts.missing_scripts += GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(node.gameObject);
                foreach (Component component in node.GetComponents<Component>())
                {
                    if (component == null) continue;
                    string type = component.GetType().FullName;
                    if (IsDescriptor(component.GetType())) descriptors.Add(component);
                    if (type == "nadena.dev.modular_avatar.core.ModularAvatarMergeAnimator" ||
                        type == "nadena.dev.modular_avatar.core.ModularAvatarMergeArmature" ||
                        type == "VF.VRCFury") hasMergeTool = true;
                }
            }
            facts.vrchat_descriptor_count = descriptors.Count;
            foreach (Renderer renderer in root.GetComponentsInChildren<Renderer>(true))
            {
                facts.renderer_count++;
                // sharedMaterials reads references without instantiating/changing materials.
                Material[] materials = renderer.sharedMaterials;
                foreach (Material material in materials)
                {
                    if (material == null) facts.missing_material_slots++;
                    else if (material.shader == null || material.shader.name == "Hidden/InternalErrorShader")
                        facts.missing_shaders++;
                }
                Mesh mesh = null;
                var skinned = renderer as SkinnedMeshRenderer;
                if (skinned != null) mesh = skinned.sharedMesh;
                else if (renderer is MeshRenderer)
                {
                    var filter = renderer.GetComponent<MeshFilter>();
                    if (filter != null) mesh = filter.sharedMesh;
                }
                if (mesh != null) facts.missing_material_slots += Math.Max(0, mesh.subMeshCount - materials.Length);
            }

            var checkedClips = new HashSet<Tuple<GameObject, AnimationClip>>();
            foreach (Animator animator in root.GetComponentsInChildren<Animator>(true))
            {
                Avatar avatar = animator.avatar;
                if (avatar != null)
                {
                    var importer = AssetImporter.GetAtPath(AssetDatabase.GetAssetPath(avatar)) as ModelImporter;
                    bool humanoid = avatar.isHuman || (importer != null &&
                        importer.animationType == ModelImporterAnimationType.Human);
                    if (humanoid && (!avatar.isValid || !avatar.isHuman)) facts.invalid_humanoid_avatars++;
                }
                CheckController(animator.runtimeAnimatorController, animator.gameObject,
                    facts, checkedClips, hasMergeTool);
            }
            foreach (Animation animation in root.GetComponentsInChildren<Animation>(true))
                foreach (AnimationClip clip in AnimationUtility.GetAnimationClips(animation.gameObject))
                    CheckClip(clip, animation.gameObject, facts, checkedClips, hasMergeTool);
            foreach (Component descriptor in descriptors)
            {
                // SerializedObject reads custom SDK layer references without an SDK dependency.
                using (var serialized = new SerializedObject(descriptor))
                    foreach (string layerName in new[] { "baseAnimationLayers", "specialAnimationLayers" })
                    {
                        SerializedProperty layers = serialized.FindProperty(layerName);
                        if (layers == null || !layers.isArray) continue;
                        for (int index = 0; index < layers.arraySize; index++)
                        {
                            SerializedProperty layer = layers.GetArrayElementAtIndex(index);
                            SerializedProperty isDefault = layer.FindPropertyRelative("isDefault");
                            if (isDefault != null && isDefault.propertyType == SerializedPropertyType.Boolean
                                && isDefault.boolValue) continue;
                            SerializedProperty controller = layer.FindPropertyRelative("animatorController");
                            if (controller != null && controller.propertyType == SerializedPropertyType.ObjectReference)
                                CheckController(controller.objectReferenceValue as RuntimeAnimatorController,
                                    descriptor.gameObject, facts, checkedClips, hasMergeTool);
                        }
                    }
            }
            return report;
        }

        private static void CheckController(RuntimeAnimatorController controller, GameObject root,
            Observations facts, HashSet<Tuple<GameObject, AnimationClip>> checkedClips, bool conditional)
        {
            if (controller == null) return;
            foreach (AnimationClip clip in controller.animationClips)
                CheckClip(clip, root, facts, checkedClips, conditional);
        }

        private static void CheckClip(AnimationClip clip, GameObject root, Observations facts,
            HashSet<Tuple<GameObject, AnimationClip>> checkedClips, bool conditional)
        {
            if (clip == null || !checkedClips.Add(Tuple.Create(root, clip))) return;
            foreach (EditorCurveBinding binding in AnimationUtility.GetCurveBindings(clip))
                CheckBinding(root, binding, facts, conditional);
            foreach (EditorCurveBinding binding in AnimationUtility.GetObjectReferenceCurveBindings(clip))
                CheckBinding(root, binding, facts, conditional);
        }

        private static void CheckBinding(GameObject root, EditorCurveBinding binding,
            Observations facts, bool conditional)
        {
            facts.checked_animation_bindings++;
            // Native resolution includes both relative transform paths and component types.
            if (AnimationUtility.GetAnimatedObject(root, binding) != null) return;
            facts.missing_animation_bindings++;
            // This subset means an existing build tool MAY rewrite/add targets, not that it will.
            if (conditional) facts.conditional_animation_bindings++;
        }

        private static bool IsDescriptor(Type type)
        {
            for (; type != null; type = type.BaseType)
                if (type.FullName == "VRC.SDK3.Avatars.Components.VRCAvatarDescriptor" ||
                    type.FullName == "VRC.SDKBase.VRC_AvatarDescriptor") return true;
            return false;
        }

        private static string SafeSubject(string name)
        {
            var result = new StringBuilder();
            foreach (char value in name)
            {
                if (result.Length >= 120) break;
                result.Append(char.IsControl(value) || value == '/' || value == '\\' ? '_' : value);
            }
            return string.IsNullOrWhiteSpace(result.ToString()) ? "unnamed" : result.ToString().Trim();
        }
    }
}
