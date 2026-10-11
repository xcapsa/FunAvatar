// Copy explicitly into Assets/Editor. Unity 2022.3+; no SDK assembly references.
// Reads the selected hierarchy and existing assets only. Does not save or upload.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using UnityEditor;
using PackageInfo = UnityEditor.PackageManager.PackageInfo;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace FunAvatar
{
    public static class FunAvatarReport
    {
        [Serializable]
        public sealed class Source
        {
            public string kind = "unity_scene";
            public string state = "unknown";
            public string hash_algorithm = "unity_dependency_hash128";
            public string hash = "";
        }

        [Serializable]
        public sealed class PackageVersion
        {
            public string name;
            public string version;
        }

        [Serializable]
        public sealed class Provenance
        {
            public string collector = "funavatar.unity_report";
            public string collector_version = "2.0.0";
            public string native_target;
            public Source source = new Source();
            public string packages_state = "unknown";
            public PackageVersion[] packages = new PackageVersion[0];
        }

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
            public int schema_version = 2;
            public string tool = "unity";
            public string tool_version;
            public string subject;
            public Observations observations = new Observations();
            public Provenance provenance;
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
                subject = SafeSubject(root.name), provenance = CollectProvenance(root) };
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

        private static Provenance CollectProvenance(GameObject root)
        {
            var result = new Provenance { native_target = EditorUserBuildSettings.activeBuildTarget.ToString() };
            try
            {
                var packages = new SortedDictionary<string, string>(StringComparer.Ordinal);
                foreach (PackageInfo package in PackageInfo.GetAllRegisteredPackages())
                {
                    // Only public SDK/engine/build-tool identities; never resolvedPath or registry URLs.
                    if (!(package.name.StartsWith("com.unity.", StringComparison.Ordinal) ||
                          package.name == "com.vrchat.base" || package.name == "com.vrchat.avatars" ||
                          package.name == "nadena.dev.ndmf" || package.name == "nadena.dev.modular-avatar" ||
                          package.name == "com.vrcfury.vrcfury")) continue;
                    if (!Regex.IsMatch(package.name, @"^[a-z0-9][a-z0-9.-]{0,127}$")) continue;
                    packages[package.name] = package.version != null && package.version.Length <= 128 &&
                        Regex.IsMatch(package.version, @"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.+-]+)?$")
                        ? package.version : "unknown";
                }
                var versions = new List<PackageVersion>();
                foreach (var package in packages)
                    versions.Add(new PackageVersion { name = package.Key, version = package.Value });
                result.packages = versions.ToArray();
                result.packages_state = "observed";
            }
            catch (Exception) { /* Unavailable package metadata stays unknown; no exception text is exported. */ }

            try
            {
                string assetPath = AssetDatabase.GetAssetPath(root);
                bool modified = EditorUtility.IsDirty(root);
                var stage = PrefabStageUtility.GetCurrentPrefabStage();
                if (stage != null && root.scene == stage.scene)
                {
                    assetPath = stage.assetPath;
                    modified |= stage.scene.isDirty;
                }
                if (!string.IsNullOrEmpty(assetPath)) result.source.kind = "unity_asset";
                else
                {
                    assetPath = root.scene.path;
                    modified |= root.scene.isDirty;
                }
                if (string.IsNullOrEmpty(assetPath))
                {
                    result.source.state = "unsaved";
                    return result;
                }
                foreach (Transform node in root.GetComponentsInChildren<Transform>(true))
                {
                    modified |= EditorUtility.IsDirty(node.gameObject);
                    foreach (Component component in node.GetComponents<Component>())
                        if (component != null) modified |= EditorUtility.IsDirty(component);
                }
                Hash128 hash = AssetDatabase.GetAssetDependencyHash(assetPath);
                foreach (string dependency in AssetDatabase.GetDependencies(assetPath, true))
                    foreach (UnityEngine.Object asset in AssetDatabase.LoadAllAssetsAtPath(dependency))
                        if (asset != null) modified |= EditorUtility.IsDirty(asset);
                if (modified) result.source.state = "modified";
                else if (hash.isValid && hash == AssetDatabase.GetAssetDependencyHash(assetPath))
                {
                    result.source.state = "saved";
                    result.source.hash = hash.ToString();
                }
            }
            catch (Exception) { /* A missing/unreadable source remains unknown, without a saved fingerprint. */ }
            return result;
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
