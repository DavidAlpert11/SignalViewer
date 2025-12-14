# Runtime hook to fix numpy docstring issue in PyInstaller
# This runs before the main script

import sys

# Fix for numpy add_docstring issue in frozen applications
def _patch_numpy_docstring():
    """Patch numpy's add_docstring to handle frozen apps."""
    try:
        import numpy.core._multiarray_umath as mu
        original_add_docstring = mu.add_docstring
        
        def patched_add_docstring(obj, docstring):
            if docstring is None:
                docstring = ''
            return original_add_docstring(obj, str(docstring))
        
        mu.add_docstring = patched_add_docstring
    except Exception:
        pass

# Apply patch early
if getattr(sys, 'frozen', False):
    _patch_numpy_docstring()
