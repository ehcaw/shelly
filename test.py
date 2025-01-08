import os
from utils.utils import find_files_in_directory, get_nth_related_files, build_adjacency_list, error_repomix
from repomixer.stack_trace_parser import StackTraceParser
from repomixer.context_collector import ContextCollector

cwd = os.getcwd()

#print(find_files_in_directory(cwd, ["yarn.lock"]))
#adj_list = build_adjacency_list(["/Users/ryannguyen/projects/typescript/tutorportal/src/components/dashboard/dashboard/AttendancePanel.tsx"], "/projects/typescript/tutorportal")
#print(get_nth_related_files(["/Users/ryannguyen/projects/typescript/tutorportal/src/components/dashboard/dashboard/AttendancePanel.tsx"], adj_list))
#print(repomix("test.py", ""))

parser = StackTraceParser("/projects/python/splat")
error_trace = """Traceback (most recent call last):
  File "/Users/ryannguyen/projects/python/splat/foo.py", line 6, in <module>
    from top.a import func_a
  File "/Users/ryannguyen/projects/python/splat/top/a.py", line 2, in <module>
    from a.y import func_y
  File "/Users/ryannguyen/projects/python/splat/a/y.py", line 2
    print("Noooope.)
          ^
SyntaxError: unterminated string literal (detected at line 2)"""
'''
primary_files = parser.extract_files(error_trace)
print(f'primary files: {primary_files}')

all_files = parser.get_related_files(primary_files)
print(f'all files: {all_files}')
'''
#rror_repomix("/projects/python/zap/foo.py", "", "")
context_collector = ContextCollector("/Users/ryannguyen/projects/python/calhacks24")
related_files = context_collector.collect_context("", "foo.py")
print(related_files)
