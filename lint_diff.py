#!/usr/bin/python

import re

def process_diff_list(fh):
    '''Obtain the filenames and locations that represent new/changed code from
    the output of the diff command and return a dict of sets describing them.'''

    diff_pattern = re.compile(r'^[,\d]+[ac](?P<start>\d+)(,(?P<end>\d+))?')
    file_pattern = re.compile(r'^diff .* (?P<file>\S+)$')
    cur_file = None
    diff_list = {}

    for line in fh:
        m = file_pattern.search(line)
        if m:
            cur_file = m.group('file')
            continue

        m = diff_pattern.search(line)
        if not m:
            continue

        if cur_file not in diff_list:
            diff_list[cur_file] = set()

        start = int(m.group('start'))
        end = start
        if m.group('end'):
            end = int(m.group('end'))

        for i in xrange(start, end + 1):
            diff_list[cur_file].add(i)

    return diff_list


def process_lint_output(fh, diff_list):
    '''Process the output from linting, filter messages not related to
    new/changed code, print the ones that are.'''

    messages = get_messages(fh)
    for locations, message_list in messages:
        if not locations:
            print ''.join(message_list),
            continue

        for filename, lineno in locations:
            if filename in diff_list and lineno in diff_list[filename]:
                print ''.join(message_list),
                break


def get_messages(fh):
    '''Process the next message group and return it along with all of the
    file locations it references'''

    # Pattern for lint messages, only need filename, line, and message number
    message_pattern = re.compile(r'^(?P<filename>[^:]*):\s*(?P<lineno>\d+):'
            r'\s*(Warning|Error|Info|Note)\s*(?P<msgno>\d+)')

    # The pattern that specifies verbose messages that are not specific
    # to a particular message and should never be suppressed
    verbose_pattern = re.compile(r'^(---|///|===|\s{4})')

    # List of tuples representing locations related to the current message
    locations = []

    # List of lines representing the current message
    buffer = []

    # Flag indicating if the contents of the current buffer contains a
    # recorgnized lint message with file information
    in_message = False

    for line in fh:
        # If line is a verbose line, emit buffer and line
        m = verbose_pattern.search(line)
        if m:
            if buffer:
                yield locations, buffer
            yield [], line
            locations = []
            buffer = []
            in_message = False
            continue

        else:
            m = message_pattern.search(line)
            if m:
                filename = m.group('filename')
                lineno = int(m.group('lineno'))
                msgno = m.group('msgno')

                if in_message and msgno not in ('830', '831'):
                    # A new message has been encountered, emit current
                    # message and queue this one
                    yield locations, buffer
                    locations = []
                    buffer = []
                    locations.append((filename, lineno))
                    buffer.append(line)
                    continue
                else:
                    # New message or 830/831 to be grouped with current one
                    in_message = True
                    locations.append((filename, lineno))
                    buffer.append(line)
                    continue

            else:
                if in_message:
                    # Message that doesn't match pattern starts a new message
                    # group, emit current message and queue new one
                    yield locations, buffer
                    locations = []
                    buffer = []
                    buffer.append(line)
                    in_message = False
                    continue
                else:
                    # If we haven't seen a recognized message yet, just add
                    # this line to the buffer
                    buffer.append(line)
                    continue

    # Don't forget to send any leftover data
    yield locations, buffer

 
if __name__ == '__main__':
    import sys
    import subprocess

    if len(sys.argv) < 4:
        print "Usage: lint_diff.py orig_dir new_dir [lint options] files"
        sys.exit(1)

    orig_dir = sys.argv[1]
    new_dir = sys.argv[2]
    lint_args = sys.argv[3:]

    diff_fh = subprocess.Popen(('diff', '-N', orig_dir, new_dir), stdout=subprocess.PIPE)
    diff_list = process_diff_list(diff_fh.stdout)

    lint_fh = subprocess.Popen((('lint',) + tuple(lint_args)), stdout=subprocess.PIPE)
    process_lint_output(lint_fh.stdout, diff_list)
