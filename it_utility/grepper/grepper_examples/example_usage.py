"""Example: using Grepper utility functions from code.

Run with: python grepper_examples/example_usage.py
"""
from grepper import fmt_size, load_gitignore_rules

def main():
    print(fmt_size(2048))
    rules = load_gitignore_rules('.')
    print('Loaded', len(rules), '.gitignore rules')

if __name__ == '__main__':
    main()
