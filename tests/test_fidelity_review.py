"""Review gate behavior, including user rejection and stale evidence."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/funavatar/scripts'
sys.path.insert(0, str(SCRIPTS))
import fidelity_review as checker


class FidelityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.asset = self.file('avatar.blend', b'actual opaque model: 64 bones; 237 technical tests passed')
        self.refs = []
        self.comparisons = []
        for identifier, view, role in [('original', 'multiview_sheet', 'primary'),
                                       ('front', 'front', 'supporting'), ('left', 'left', 'supporting'),
                                       ('right', 'right', 'supporting')]:
            self.refs.append({'id': identifier, 'view': view, 'role': role, 'availability': 'available',
                              **self.file(identifier + '.png', ('reference-' + identifier).encode()),
                              'note': 'Original supplied view, preserved in this inventory.'})
            self.comparisons.append({'reference_id': identifier,
                                     'render': self.file('render-' + identifier + '.png', b'native rendered pixels'),
                                     'render_view': 'front' if view == 'multiview_sheet' else view,
                                     'camera_pose_compatible': True, 'status': 'pass',
                                     'note': 'Reviewer compared the corresponding silhouette and garments.'})
        self.inventory = {'schema_version': 1, 'references': self.refs}
        self.review = {'schema_version': 1, 'asset': self.asset, 'reference_set': self.save_inventory(),
                       'comparisons': self.comparisons,
                       'categories': {name: {'status': 'pass', 'note': 'Named reference features compared by reviewer.',
                                            'reference_ids': ['original', 'front', 'left', 'right']}
                                      for name in checker.CATEGORIES},
                       'user_rejection': {'rejected': False, 'note': 'No user rejection recorded.'}}

    def file(self, name, content):
        (self.root / name).write_bytes(content)
        return {'path': name, 'sha256': hashlib.sha256(content).hexdigest()}

    def save_inventory(self):
        return self.file('reference-set.json', json.dumps(self.inventory).encode())

    def check(self):
        return checker.check(self.review, self.root)

    def codes(self):
        return {issue['code'] for issue in self.check()['issues']}

    def call(self, *args):
        with redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()) as error:
            code = checker.main(list(args))
        return code, output.getvalue(), error.getvalue()

    def write_review(self):
        path = self.root / 'review.json'
        path.write_text(json.dumps(self.review))
        return path

    def test_complete_review_uses_faithful_default_without_claiming_pixel_judgment(self):
        result = self.check()
        self.assertTrue(result['can_proceed_to_production_rig'])
        self.assertTrue(result['can_claim_fidelity'])
        self.assertEqual(result['intent'], 'faithful_reconstruction')
        self.assertFalse(result['visual_judgment_performed'])
        self.assertIn('does not judge pixels', result['scope'])
        self.assertEqual(result['reference_roles']['original'], 'primary')

    def test_user_rejection_overrides_every_pass_and_technical_success(self):
        self.review['user_rejection'] = {'rejected': True,
            'note': 'The result differs substantially from my supplied character photo.'}
        result = self.check()
        self.assertFalse(result['can_proceed_to_production_rig'])
        self.assertFalse(result['can_claim_fidelity'])
        self.assertIn('user_rejected', {issue['code'] for issue in result['issues']})
        self.assertEqual(self.call('check', str(self.write_review()))[0], 1)

    def test_each_core_category_can_independently_block_a_complete_review(self):
        for category in checker.CATEGORIES:
            with self.subTest(category=category):
                self.review['categories'][category]['status'] = 'needs_repair'
                self.review['categories'][category]['note'] = 'Observed left and right accessory placement is reversed.'
                self.assertFalse(self.check()['can_proceed_to_production_rig'])
                self.review['categories'][category]['status'] = 'pass'

    def test_unreviewed_missing_category_and_missing_supplied_view_block(self):
        self.review['categories'].pop('materials')
        self.review['comparisons'] = self.comparisons[:-1]
        self.assertTrue({'unreviewed_category', 'missing_view_comparison'} <= self.codes())
        self.assertFalse(self.check()['can_claim_fidelity'])

    def test_declared_camera_incompatibility_is_a_valid_blocked_review(self):
        self.comparisons[1]['camera_pose_compatible'] = False
        self.comparisons[1]['render_view'] = 'back'
        self.comparisons[1]['status'] = 'needs_repair'
        self.assertTrue({'camera_pose_not_comparable', 'declared_view_mismatch', 'needs_repair'} <= self.codes())
        self.assertEqual(self.call('check', str(self.write_review()))[0], 1)

    def test_stale_asset_reference_render_and_inventory_each_block(self):
        for name in ['avatar.blend', 'original.png', 'render-front.png', 'reference-set.json']:
            with self.subTest(file=name):
                path = self.root / name
                previous = path.read_bytes()
                path.write_bytes(previous + b' ')
                self.assertIn('stale_evidence', self.codes())
                self.assertFalse(self.check()['can_proceed_to_production_rig'])
                path.write_bytes(previous)

    def test_dropping_an_original_view_or_changing_roles_invalidates_inventory_binding(self):
        self.inventory['references'] = self.refs[1:]
        self.save_inventory()  # Existing review still pins the original complete inventory.
        self.assertIn('stale_evidence', self.codes())
        self.assertIn('missing_primary_reference', self.codes())
        self.assertFalse(self.check()['can_claim_fidelity'])

    def test_comparisons_cannot_override_reference_roles(self):
        self.comparisons[0]['role'] = 'supporting'
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_file_unavailable_view_and_absent_render_never_pass(self):
        (self.root / 'avatar.blend').unlink()
        self.refs[2].update(availability='unavailable', path=None, sha256=None,
                            note='The original left-side file was supplied but cannot currently be read.')
        self.review['reference_set'] = self.save_inventory()
        self.comparisons[2]['render'] = None
        self.comparisons[2]['status'] = 'not_assessed'
        self.assertTrue({'missing_file', 'unavailable_reference', 'missing_comparison_render', 'not_assessed'} <= self.codes())
        self.assertFalse(self.check()['can_proceed_to_production_rig'])

    def test_unknown_reference_id_and_category_evidence_block(self):
        self.comparisons[0]['reference_id'] = 'invented'
        self.review['categories']['branding']['reference_ids'] = ['invented']
        self.assertTrue({'unknown_reference', 'missing_view_comparison', 'category_evidence_missing'} <= self.codes())

    def test_unknown_views_and_duplicate_reference_ids_are_invalid_not_accepted(self):
        self.refs[1]['view'] = 'frnot'
        self.review['reference_set'] = self.save_inventory()
        with self.assertRaises(ValueError):
            self.check()
        self.refs[1]['view'] = 'front'
        self.refs[1]['id'] = 'original'
        self.review['reference_set'] = self.save_inventory()
        with self.assertRaises(ValueError):
            self.check()

    def test_literal_authorization_is_required_for_reinterpretation(self):
        self.review['intent'] = 'reinterpretation'
        self.assertIn('reinterpretation_not_authorised', self.codes())
        self.review['authorised_change'] = {'quote': 'I approve the proposed stylized reinterpretation.',
            'evidence': self.file('change.txt', b'I approve the proposed stylized reinterpretation.')}
        result = self.check()
        self.assertTrue(result['can_proceed_to_production_rig'])
        self.assertFalse(result['can_claim_fidelity'])
        self.review['authorised_change']['quote'] = 'I approve an entirely different character.'
        self.assertIn('authorization_quote_not_found', self.codes())

    def test_authorized_reinterpretation_never_overrides_later_user_rejection(self):
        self.review['intent'] = 'reinterpretation'
        self.review['authorised_change'] = {'quote': 'Approved style', 'evidence': self.file('change.txt', b'Approved style')}
        self.review['user_rejection'] = {'rejected': True, 'note': 'This still does not match the agreed design.'}
        self.assertFalse(self.check()['can_proceed_to_production_rig'])

    def test_strict_types_notes_and_unknown_success_flags_are_rejected(self):
        original = copy.deepcopy(self.review)
        for key, value in [('schema_version', True), ('schema_version', 1.0), ('schema_version', '1'),
                           ('quality_pass', True), ('technical_tests_passed', 237)]:
            with self.subTest(field=key, value=value):
                self.review = {**copy.deepcopy(original), key: value}
                with self.assertRaises(ValueError):
                    self.check()
        self.review = copy.deepcopy(original)
        for value in (1, 'true', None):
            self.review['user_rejection']['rejected'] = value
            with self.assertRaises(ValueError):
                self.check()
        self.review = copy.deepcopy(original)
        self.review['categories']['silhouette']['note'] = '   '
        with self.assertRaises(ValueError):
            self.check()

    def test_duplicate_json_keys_and_nonfinite_numbers_never_reach_acceptance(self):
        path = self.root / 'invalid.json'
        for raw in ['{"schema_version":1,"schema_version":1}', '{"nested":{"x":1,"x":2}}',
                    '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}']:
            with self.subTest(raw=raw):
                path.write_text(raw)
                self.assertEqual(self.call('check', str(path))[0], 2)

    def test_new_output_is_receipt_bound_and_existing_output_is_preserved(self):
        path = self.write_review()
        out = self.root / 'result.json'
        code, _, _ = self.call('check', str(path), '--out', str(out))
        self.assertEqual(code, 0)
        result = json.loads(out.read_text())
        self.assertEqual(result['bindings'][0]['sha256'], self.asset['sha256'])
        previous = out.read_bytes()
        self.review['user_rejection']['rejected'] = True
        self.write_review()
        self.assertEqual(self.call('check', str(path), '--out', str(out))[0], 2)
        self.assertEqual(out.read_bytes(), previous)

    def test_symlink_input_and_symlink_output_are_not_followed(self):
        path = self.write_review()
        alias = self.root / 'alias.json'
        try:
            alias.symlink_to(path)
        except OSError:
            self.skipTest('Symlinks unavailable on this host')
        self.assertEqual(self.call('check', str(alias))[0], 2)
        previous = path.read_bytes()
        self.assertEqual(self.call('check', str(path), '--out', str(alias))[0], 2)
        self.assertEqual(path.read_bytes(), previous)


    def sentinel_command(self, exit_code=0):
        script = self.root / 'child.py'
        script.write_text("import json,sys; from pathlib import Path; "
                          "Path(sys.argv[1]).write_text(json.dumps(sys.argv[3:])); "
                          "sys.exit(int(sys.argv[2]))")
        sentinel = self.root / 'sentinel.json'
        return sentinel, [sys.executable, str(script), str(sentinel), str(exit_code)]

    def test_run_rechecks_current_review_and_stale_asset_before_starting_child(self):
        sentinel, command = self.sentinel_command()
        path = self.write_review()
        self.assertEqual(self.call('check', str(path))[0], 0)
        self.review['user_rejection']['rejected'] = True
        self.write_review()
        self.assertEqual(self.call('run', str(path), '--', *command)[0], 1)
        self.assertFalse(sentinel.exists())
        self.review['user_rejection']['rejected'] = False
        self.write_review()
        (self.root / 'avatar.blend').write_bytes(b'changed since prior successful review')
        self.assertEqual(self.call('run', str(path), '--', *command)[0], 1)
        self.assertFalse(sentinel.exists())
        path.write_text('{"schema_version":true}')
        self.assertEqual(self.call('run', str(path), '--', *command)[0], 2)
        self.assertFalse(sentinel.exists())

    def test_run_starts_real_child_and_preserves_its_nonzero_exit_and_literal_arguments(self):
        sentinel, command = self.sentinel_command(exit_code=23)
        literal = '; echo should-not-be-interpreted $(never-execute)'
        code, output, _ = self.call('run', str(self.write_review()), '--', *command, literal, '--out')
        self.assertEqual(code, 23)
        self.assertEqual(json.loads(sentinel.read_text()), [literal, '--out'])
        self.assertTrue(json.loads(output)['can_proceed_to_production_rig'])

    def test_run_cli_requires_separator_executable_and_rejects_wrapper_out(self):
        sentinel, command = self.sentinel_command()
        path = str(self.write_review())
        out = self.root / 'must-not-write.json'
        for args in [('run', path, *command), ('run', path, '--'),
                     ('run', path, '--out', str(out), '--', *command)]:
            with self.subTest(args=args):
                completed = subprocess.run([sys.executable, str(SCRIPTS / 'fidelity_review.py'), *args],
                                           capture_output=True, text=True, check=False)
                self.assertEqual(completed.returncode, 2)
                self.assertFalse(sentinel.exists())
                self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
