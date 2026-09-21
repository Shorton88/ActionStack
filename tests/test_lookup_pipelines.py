import unittest
from unittest.mock import Mock
import test_pages as fx
from actionstack.core import Error,seed_form,validate_definition,validate_inputs,approval_policy
from actionstack.lookups import validate_source,lookup_spl,LookupSearch

CONFIG={'search':'| inputlookup identities | eval display=first . " " . last | table identity display','value_field':'identity','label_field':'display','app':'search','min_chars':3,'debounce_ms':50}
class LookupPipelines(unittest.TestCase):
 def test_transformations_execute_before_matching_both_columns(self):
  spl,column=lookup_spl(CONFIG,'Alice')
  self.assertEqual(column,'identity');self.assertIn('eval display=first . " " . last | table identity display | where',spl)
  self.assertIn("lower(tostring('identity'))",spl);self.assertIn("lower(tostring('display'))",spl)
  self.assertTrue(spl.endswith('| fields identity display'));self.assertIn('inputlookup strict=true identities',spl)
 def test_quoted_pipes_and_regex_brackets_are_not_pipeline_commands(self):
  c=dict(CONFIG,search='| inputlookup identities | eval display="a | b" | rex field=identity "(?<part>[a-z]+)" | table identity display')
  self.assertEqual(validate_source(c),('identity','display'))
 def test_disallowed_commands_subsearches_and_macros_fail_closed(self):
  for tail in ['| outputlookup x','| collect index=x','| sendemail to=x','| map search="x"','| eval display=[|inputlookup x]','| `macro`','| eval display="unterminated','|| fields identity']:
   with self.subTest(tail=tail),self.assertRaises(Error):validate_source(dict(CONFIG,search='| inputlookup identities '+tail))
 def test_all_supported_transformations_and_mapping_identifiers(self):
  validate_source(dict(CONFIG,search='| inputlookup identities | rename email AS identity | where isnotnull(identity) | stats count by identity display | sort display | table identity display'))
  for field in ['identity | delete',"id'",'',None]:
   with self.subTest(field=field),self.assertRaises(Error):validate_source(dict(CONFIG,value_field=field))
 def test_value_is_validated_exactly_not_its_label(self):
  spl,_=lookup_spl(CONFIG,['user-1','user-2'],True)
  self.assertIn("tostring('identity') = \"user-1\"",spl);self.assertNotIn("tostring('display')",spl);self.assertIn('head 2',spl)
 def test_label_matches_return_the_underlying_value(self):
  rest=Mock();rest.call.side_effect=[{'sid':'1'},{'entry':[{'content':{'isDone':True}}]},{'results':[{'identity':'uid-17','display':'Alice Example'},{'identity':'uid-17','display':'Alice duplicate'}]},{}]
  result=LookupSearch(rest,'requester').search(CONFIG,'ali')
  self.assertEqual(result['options'],[{'value':'uid-17','label':'Alice Example'}]);self.assertEqual(rest.call.call_args.args[0],'DELETE')
 def test_missing_projected_field_is_actionable(self):
  rest=Mock();rest.call.side_effect=[{'sid':'1'},{'entry':[{'content':{'isDone':True}}]},{'results':[{'identity':'alice'}]},{}]
  with self.assertRaises(Error) as e:LookupSearch(rest,'requester').search(CONFIG,'ali')
  self.assertIn('value or label field',e.exception.message)
 def test_collapsed_sections_do_not_skip_required_input_validation(self):
  f=seed_form();f['mapping']['policy']='none';f['fields']=[{'key':'section','type':'section','label':'Details','collapsed':True},{'key':'name','type':'text','label':'Name','required':True}]
  validate_definition(f,fx.ROLES)
  with self.assertRaises(Error) as e:validate_inputs(f,{})
  self.assertIn('name',e.exception.fields)
  self.assertEqual(validate_inputs(f,{'name':'Alice'}),{'name':'Alice'})
  f['fields'][0]['collapsed']='yes'
  with self.assertRaises(Error):validate_definition(f,fx.ROLES)
 def test_approval_routes_to_soar_playbook(self):
  f=seed_form();f['mapping']['approval']={'mode':'always','conditions':[],'policy':'soar_playbook'}
  validate_definition(f,fx.ROLES)
  self.assertEqual(approval_policy(f,{}),{'approval_required':True,'approval_policy':'soar_playbook'})
