"""Exercise exact CLI dispatch AST with image-producing functions stubbed."""
import ast
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

TARGET=Path(os.environ.get('RIG_SOURCE', str(Path(__file__).parents[1]/'tools/prepare_rig.py')))

class DispatchTests(unittest.TestCase):
    def invoke(self, argv, front_error=None, side_error=None):
        calls=[]
        def front():
            calls.append('front')
            if front_error:raise front_error
        def side():
            calls.append('side')
            if side_error:raise side_error
        module=types.ModuleType('prepare_side');module.main=Mock(side_effect=side)
        tree=ast.parse(TARGET.read_text())
        nodes=[node for node in tree.body if
               isinstance(node, ast.FunctionDef) and node.name=='main' or
               isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
               and isinstance(node.test.left, ast.Name) and node.test.left.id=='__name__']
        self.assertTrue(nodes, 'CLI entrypoint missing')
        namespace={'__name__':'__main__','front':front,'sys':sys}
        with patch.dict(sys.modules, {'prepare_side':module}),patch.object(sys,'argv',['prepare_rig.py',*argv]):
            exec(compile(ast.Module(body=nodes,type_ignores=[]),str(TARGET),'exec'),namespace)
        return calls,module.main
    def test_default_front_only(self):
        calls,side=self.invoke([]);self.assertEqual(calls,['front']);side.assert_not_called()
    def test_side_calls_front_then_side(self):
        calls,side=self.invoke(['--side']);self.assertEqual(calls,['front','side']);side.assert_called_once_with()
    def test_repeated_flag_does_not_repeat_side(self):
        calls,side=self.invoke(['--side','--side']);self.assertEqual(calls,['front','side']);side.assert_called_once_with()
    def test_front_failure_stops(self):
        with self.assertRaisesRegex(RuntimeError,'front failed'):self.invoke(['--side'],front_error=RuntimeError('front failed'))
    def test_side_failure_propagates(self):
        with self.assertRaisesRegex(RuntimeError,'side failed'):self.invoke(['--side'],side_error=RuntimeError('side failed'))

if __name__=='__main__':unittest.main()
