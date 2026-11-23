try:
    from unittest import TestCase
    from mock import patch, Mock, call
except ImportError:
    from unittest import TestCase
    from mock import patch, Mock, call

import os
import six

from cfn_sphere import StackActionHandler
from cfn_sphere.aws.cfn import CloudFormationStack
from cfn_sphere.stack_configuration import Config


class StackActionHandlerTests(TestCase):
    @patch.dict(os.environ, {'GITHUB_REPOSITORY': 'Scout24/New-Repository'}, clear=True)
    @patch('cfn_sphere.CloudFormation')
    @patch('cfn_sphere.ParameterResolver')
    @patch('cfn_sphere.TemplateHandler.get_template')
    @patch.object(Config, '_find_metadata_file', return_value='metadata.yaml')
    @patch('cfn_sphere.stack_configuration.FileLoader.get_yaml_or_json_file')
    @patch('cfn_sphere.stack_configuration.get_logger')
    def test_resolved_tags_reach_both_create_and_update(self, logger, load_metadata, find_metadata,
                                                       get_template, parameter_resolver, cfn):
        for exists in (False, True):
            for metadata in ({'id': 'legacy-service'}, {}):
                for metadata_present in (True, False):
                    with self.subTest(exists=exists, metadata=metadata, metadata_present=metadata_present):
                        load_metadata.return_value = metadata
                        find_metadata.return_value = 'metadata.yaml' if metadata_present else None
                        logger.reset_mock()
                        config = Config(config_dict={
                            'region': 'eu-west-1',
                            'tags': {'service-id': 'default-service', 'component-id': 'Scout24/default', 'custom': 'default'},
                            'stacks': {'stack': {'template-url': 'template.yml', 'tags': {
                                'service-id': 'stack-service', 'component-id': 'Scout24/stack', 'custom': 'stack'}}},
                        }, cli_tags='service-id=cli-service component-id=Scout24/cli custom=cli')
                        cfn.return_value.reset_mock()
                        cfn.return_value.stack_exists.return_value = exists
                        handler = StackActionHandler(config)
                        handler.create_or_update_stacks()

                        action = cfn.return_value.update_stack if exists else cfn.return_value.create_stack
                        action.assert_called_once()
                        sent_stack = action.call_args[0][0]
                        expected_service = 'legacy-service' if metadata_present and metadata.get('id') else 'cli-service'
                        expected_component = 'Scout24/New-Repository'
                        self.assertEqual(expected_service, sent_stack.tags['service-id'])
                        self.assertEqual(expected_component, sent_stack.tags['component-id'])
                        self.assertEqual('cli', sent_stack.tags['custom'])
                        self.assertIn({'Key': 'service-id', 'Value': expected_service}, sent_stack.get_tags_list())
                        self.assertIn({'Key': 'component-id', 'Value': expected_component}, sent_stack.get_tags_list())
                        logger.return_value.warning.assert_any_call(
                            'Supplied component-id tag Scout24/cli is ignored; using Scout24/New-Repository')
                        if metadata_present and metadata.get('id'):
                            logger.return_value.warning.assert_any_call(
                                'metadata.yaml id legacy-service differs from the repository name New-Repository')
                            logger.return_value.warning.assert_any_call(
                                'Supplied service-id tag cli-service is ignored; using legacy-service')
                            logger.return_value.warning.assert_any_call(
                                'Supplied service-id tag stack-service is ignored; using legacy-service')

    @patch('cfn_sphere.CloudFormation')
    @patch('cfn_sphere.ParameterResolver')
    @patch('cfn_sphere.DependencyResolver')
    @patch('cfn_sphere.FileLoader')
    @patch('cfn_sphere.CloudFormationStack')
    def test_delete_stacks(self,
                           stack_mock,
                           template_loader_mock,
                           dependency_resolver_mock,
                           parameter_resolver_mock,
                           cfn_mock):

        dependency_resolver_mock.return_value.get_stack_order.return_value = ['a', 'c']
        cfn_mock.return_value.get_stack_names.return_value = ['a', 'd']

        stack_a = CloudFormationStack('', [], 'a', '')
        stack_c = CloudFormationStack('', [], 'c', '')

        def stack_side_effect(*args, **kwargs):
            if kwargs["name"] == 'a':
                return stack_a
            if kwargs["name"] == 'c':
                return stack_c
            return None

        stack_mock.side_effect = stack_side_effect

        handler = StackActionHandler(Mock())
        handler.delete_stacks()

        cfn_mock.return_value.delete_stack.assert_called_once_with(stack_a)

    @patch('cfn_sphere.CloudFormation')
    @patch('cfn_sphere.ParameterResolver')
    @patch('cfn_sphere.DependencyResolver')
    @patch('cfn_sphere.FileLoader')
    @patch('cfn_sphere.CloudFormationStack')
    def test_delete_stacks_uses_the_correct_order(self,
                                                  stack_mock,
                                                  template_loader_mock,
                                                  dependency_resolver_mock,
                                                  parameter_resolver_mock,
                                                  cfn_mock):

        dependency_resolver_mock.return_value.get_stack_order.return_value = ['a', 'c']
        cfn_mock.return_value.get_stack_names.return_value = ['a', 'c']

        stack_a = CloudFormationStack('', [], 'a', '')
        stack_c = CloudFormationStack('', [], 'c', '')

        def stack_side_effect(*args, **kwargs):
            if kwargs["name"] == 'a':
                return stack_a
            if kwargs["name"] == 'c':
                return stack_c
            return None

        stack_mock.side_effect = stack_side_effect

        handler = StackActionHandler(Mock())
        handler.delete_stacks()

        expected_calls = [call(stack_c), call(stack_a)]
        six.assertCountEqual(self, expected_calls, cfn_mock.return_value.delete_stack.mock_calls)
