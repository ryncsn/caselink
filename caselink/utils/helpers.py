from .jira import create_jira_issue, add_jira_comment


def is_pattern_match(pattern, casename):
    """
    Test if a autocase match with the name pattern.
    """
    segments = pattern.split('..')
    items = casename.split('.')
    idx = 0
    for segment in segments:
        seg_items = segment.split('.')
        try:
            while True:
                idx = items.index(seg_items[0])
                if items[idx:len(seg_items)] == seg_items:
                    items = items[len(seg_items):]
                    break
                else:
                    del items[0]
        except ValueError:
            return False
    return True
