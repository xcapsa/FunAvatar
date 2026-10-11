// Optional Unity EditMode tests: run in a disposable authorized project with Test Framework.
using System;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace FunAvatar.Tests
{
    public sealed class FunAvatarReportTests
    {
        private Scene previousScene;
        private Scene testScene;
        private GameObject root;
        private string folder;

        [SetUp]
        public void SetUp()
        {
            previousScene = SceneManager.GetActiveScene();
            testScene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
            root = new GameObject("AuditAvatar");
            SceneManager.MoveGameObjectToScene(root, testScene);
            string name = "FunAvatarReportTest-" + Guid.NewGuid().ToString("N");
            AssetDatabase.CreateFolder("Assets", name);
            folder = "Assets/" + name;
        }

        [TearDown]
        public void TearDown()
        {
            if (previousScene.IsValid() && previousScene.isLoaded) SceneManager.SetActiveScene(previousScene);
            if (testScene.IsValid() && testScene.isLoaded) EditorSceneManager.CloseScene(testScene, true);
            if (!string.IsNullOrEmpty(folder)) AssetDatabase.DeleteAsset(folder);
        }

        [Test]
        public void UnsavedSceneHasNoFingerprintAndRecordsActualTarget()
        {
            var report = FunAvatarReport.Collect(root);
            Assert.AreEqual(2, report.schema_version);
            Assert.AreEqual("unsaved", report.provenance.source.state);
            Assert.AreEqual("", report.provenance.source.hash);
            Assert.AreEqual(EditorUserBuildSettings.activeBuildTarget.ToString(), report.provenance.native_target);
            StringAssert.DoesNotContain(folder, JsonUtility.ToJson(report));
            StringAssert.DoesNotContain(Application.dataPath, JsonUtility.ToJson(report));
        }

        [Test]
        public void SavedPrefabFingerprintMatchesNativeDependencyHashAndIsStable()
        {
            string path = folder + "/Avatar.prefab";
            PrefabUtility.SaveAsPrefabAsset(root, path);
            var saved = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            var first = FunAvatarReport.Collect(saved);
            var second = FunAvatarReport.Collect(saved);
            Assert.AreEqual("saved", first.provenance.source.state);
            Assert.AreEqual("unity_asset", first.provenance.source.kind);
            Assert.AreEqual("unity_dependency_hash128", first.provenance.source.hash_algorithm);
            Assert.AreEqual(AssetDatabase.GetAssetDependencyHash(path).ToString(), first.provenance.source.hash);
            Assert.AreEqual(first.provenance.source.hash, second.provenance.source.hash);
            StringAssert.DoesNotContain(path, JsonUtility.ToJson(first));
        }

        [Test]
        public void DirtyReferencedMaterialInvalidatesSavedPrefabFingerprint()
        {
            var shader = Shader.Find("Hidden/InternalErrorShader");
            if (shader == null) Assert.Ignore("Test requires an available built-in shader.");
            var material = new Material(shader);
            AssetDatabase.CreateAsset(material, folder + "/Material.mat");
            root.AddComponent<MeshRenderer>().sharedMaterial = material;
            string path = folder + "/Avatar.prefab";
            PrefabUtility.SaveAsPrefabAsset(root, path);
            var saved = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            material.renderQueue = 2401;
            EditorUtility.SetDirty(material);
            var report = FunAvatarReport.Collect(saved);
            Assert.AreEqual("modified", report.provenance.source.state);
            Assert.AreEqual("", report.provenance.source.hash);
        }

        [Test]
        public void MissingMaterialIsReportedInSelectedHierarchy()
        {
            root.AddComponent<MeshRenderer>().sharedMaterials = new Material[] { null };
            var report = FunAvatarReport.Collect(root);
            Assert.AreEqual(1, report.observations.renderer_count);
            Assert.AreEqual(1, report.observations.missing_material_slots);
        }

        [Test]
        public void ControllerBindingIsResolvedAgainstItsAnimatorRoot()
        {
            var controller = AnimatorController.CreateAnimatorControllerAtPath(folder + "/Controller.controller");
            var clip = new AnimationClip();
            AnimationUtility.SetEditorCurve(clip,
                EditorCurveBinding.FloatCurve("MissingChild", typeof(Transform), "m_LocalPosition.x"),
                AnimationCurve.Constant(0, 1, 0));
            AssetDatabase.CreateAsset(clip, folder + "/Clip.anim");
            controller.AddMotion(clip);
            root.AddComponent<Animator>().runtimeAnimatorController = controller;
            var report = FunAvatarReport.Collect(root);
            Assert.AreEqual(1, report.observations.checked_animation_bindings);
            Assert.AreEqual(1, report.observations.missing_animation_bindings);
        }
    }
}
