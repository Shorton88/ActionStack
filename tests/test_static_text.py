import unittest
import test_pages as fx
from actionstack.core import Error, seed_form, validate_definition, validate_inputs, event_payload, visible


def form():
    f = seed_form()
    f['mapping']['policy'] = 'none'
    f['fields'] = [
        {'key': 'enabled', 'type': 'checkbox', 'label': 'Enable change'},
        {'key': 'notice', 'type': 'static_text', 'label': 'Service interruption',
         'help': 'This change disconnects users.\nNotify your team first.', 'tone': 'warning',
         'show_when': {'field': 'enabled', 'equals': True}},
    ]
    return f


class StaticTextTests(unittest.TestCase):
    def test_static_text_styles_round_trip_with_visibility(self):
        for tone in ['text', 'info', 'warning']:
            f = form(); f['fields'][1]['tone'] = tone
            saved = validate_definition(f, fx.ROLES)
            self.assertEqual(saved['fields'][1], f['fields'][1])
            self.assertFalse(visible(saved['fields'][1], {'enabled': False}))
            self.assertTrue(visible(saved['fields'][1], {'enabled': True}))

    def test_no_input_required_and_no_static_text_in_soar_payload(self):
        f = validate_definition(form(), fx.ROLES)
        f.update(version=1, revision=1)
        for enabled in [False, True]:
            inputs = validate_inputs(f, {'enabled': enabled})
            self.assertEqual(inputs, {'enabled': enabled})
            container, artifact = event_payload(f, fx.actor(), inputs, 'sid', 'now', {})
            self.assertEqual(container['data']['actionstack']['form']['fields'], {'enabled': 'Enable change'})
            self.assertEqual(artifact['data']['actionstack']['inputs'], inputs)
            self.assertNotIn('actionstack_notice', artifact['cef'])
        with self.assertRaises(Error):
            validate_inputs(f, {'enabled': True, 'notice': 'forged'})

    def test_static_text_cannot_require_validate_or_map_input(self):
        for patch in [{'required': True}, {'default': 'x'}, {'cef_key': 'message'},
                      {'required_when': [{'field': 'enabled', 'equals': True}]},
                      {'validation': [{'operator': 'equals', 'value': 'x', 'message': 'Invalid'}]},
                      {'tone': 'unknown'}, {'help': 'x' * 2001}]:
            f = form(); f['fields'][1].update(patch)
            with self.subTest(patch=patch), self.assertRaises(Error):
                validate_definition(f, fx.ROLES)

    def test_static_text_cannot_control_other_fields(self):
        f = form()
        f['fields'].append({'key': 'name', 'type': 'text', 'label': 'Name',
                            'show_when': {'field': 'notice', 'equals': 'x'}})
        with self.assertRaises(Error): validate_definition(f, fx.ROLES)
        f = form(); f['fields'][0]['tone'] = 'info'
        with self.assertRaises(Error): validate_definition(f, fx.ROLES)

    def test_static_text_persists_through_save_and_publish(self):
        fixture = fx.ServiceTests(); fixture.setUp()
        try:
            saved = fixture.svc.save_form(fx.ADMIN, {'form': form(), 'expected_revision': 1}, True)
            self.assertEqual(fixture.svc.published(saved['id'])['fields'][1], form()['fields'][1])
        finally:
            fixture.tearDown()
