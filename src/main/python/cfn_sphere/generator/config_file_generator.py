import textwrap


def render_template():
    config_template = {
        'region': 'eu-west-1',
        'stacks': {
            {'my-stack':
                {
                    'template-url': 'my-template.url',
                    'parameters':
                        {
                            'param1': 'my-value1',
                            'param2': 'my-value2'
                        }
                }
            }
        }
    }
