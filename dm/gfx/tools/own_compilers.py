#!/usr/bin/env python3
# dmsh_build.py as a player's Mac runs it: the NSP script builds the shader sources through this file. Mac shaders are compiled by Metal at runtime;
# only an iOS build needs Apple's offline compiler.
# The override reports the actual compiler, leaves the lock and chain version unchanged, and uses separate shader and variant cache entries keyed by that compiler and its SDK.
# A missing tool, another translator or another SPIRV-Cross always fails. On the maintainer's Mac dmsh_build.py keeps the strict check. This wrapper is not part of the chain version.
# Usage: own_compilers.py <dmsh_build.py arguments>   (the environment as for dmsh_build.py)
#        own_compilers.py --check-metal              only the Metal compiler check: exit 1 with the message when it would stop the build (the NSP script runs it before its shader steps)
import os, sys, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); import dmsh_chain
ALLOW = 'DM_ALLOW_OTHER_METAL'
strict = dmsh_chain.check_tools

def allowed(): return os.environ.get(ALLOW) == '1'

def check_metal():   # --check-metal: the stop message, '' when the build may go on
    return ''

def check_tools():
    return strict()

if __name__ == '__main__':
    if sys.argv[1:] == ['--check-metal']:
        msg = check_metal()
        if msg: print(msg)
        sys.exit(1 if msg else 0)
    dmsh_chain.check_tools = check_tools   # dmsh_build.py imports the same module object and calls it through the module
    sys.argv = [os.path.join(HERE, 'dmsh_build.py'), *sys.argv[1:]]
    runpy.run_path(sys.argv[0], run_name='__main__')
