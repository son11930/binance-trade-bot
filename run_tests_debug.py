import pytest
import sys
import logging

logging.basicConfig(level=logging.DEBUG)

if __name__ == '__main__':
    sys.exit(pytest.main(['-v', '-s', 'tests/test_signal_evaluator.py']))
