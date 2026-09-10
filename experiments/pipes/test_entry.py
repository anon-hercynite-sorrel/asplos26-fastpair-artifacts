"""Offline guard tests; no GPU commands or benchmark binary are executed."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import capture


class EntryGuards(unittest.TestCase):
    def guard(self, extra):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            bench=root/'target/release/onpair-chunk-bench'
            bench.parent.mkdir(parents=True);bench.touch()
            data=root/'rebuilt.vortex';data.write_bytes(b'rebuilt test container')
            argv=['capture.py','--chip','a100','--harness',str(root),'--vortex',str(data),
                  '--output',str(root/'output'),*extra]
            stderr=io.StringIO()
            with patch('sys.argv',argv),patch.object(capture.subprocess,'check_output',return_value='a'*40+'\n') as git,patch.object(capture.shutil,'which',return_value=None),contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as result:capture.main()
            self.assertEqual(result.exception.code,2)
            self.assertFalse((root/'output').exists())
            return stderr.getvalue(),git.call_count

    def test_rebuilt_input_current_revision_reaches_gpu_preflight(self):
        message,calls=self.guard([])
        self.assertIn('ncu not found',message)
        self.assertEqual(calls,1)

    def test_explicit_input_pin_fails_before_git_or_gpu(self):
        message,calls=self.guard(['--expected-input-sha256','0'*64])
        self.assertIn('input digest differs',message)
        self.assertEqual(calls,0)

    def test_explicit_revision_pin_fails_before_gpu(self):
        message,_=self.guard(['--expected-revision','b'*40])
        self.assertIn('harness revision differs',message)

    def test_workload_validation_requires_statistics_and_byte_check(self):
        valid={'decoded_bytes':999999899,'total_tokens':99090926,'chunks':1,
               'frac_le8':.37251443,'verified':True,'validated':True}
        capture.validate_workload(valid)
        for field,value in [('decoded_bytes',1),('total_tokens',1),('chunks',2),
                            ('frac_le8',.5),('verified',False),('validated',False)]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                capture.validate_workload(dict(valid,**{field:value}))

if __name__=='__main__':unittest.main()
