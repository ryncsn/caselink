import sys
import re
import difflib
import datetime
import suds
import pytz


if sys.version_info >= (3, 0):
    from html.parser import HTMLParser
else:
    import HTMLParser

PYLARION_INSTALLED = True
try:
    from pylarion.enum_option_id import EnumOptionId
    from pylarion.work_item import _WorkItem
    from pylarion.document import Document
except ImportError:
    PYLARION_INSTALLED = False


try:
    literal = unicode
except NameError:
    literal = str


def _convert_text(text):
    """
    Convert and format HTML into plain text, clean '<br>'s
    """
    lines = re.split(r'\<[bB][rR]/\>', text)
    new_lines = []
    for line in lines:
        line = " ".join(line.split())
        if line:
            line = HTMLParser.HTMLParser().unescape(line)
            new_lines.append(line)
    return '\n'.join(new_lines)


def _diff_test_steps(before, after):
    """
    Will break if steps are not in a two columns table (Step, Result)
    """
    def _get_steps_for_diff(data):
        ret = []
        if not data:
            return ret
        try:
            steps = data.get('steps', {}).get('TestStep', [])
            if not isinstance(steps, list):
                steps = [steps]
            for idx, raw_step in enumerate(steps):
                step, result = [
                    _convert_text(text['content'])
                    for text in raw_step['values']['Text']]
                ret.extend([
                    "Step:",
                    step or "<empty>",
                    "Expected result:",
                    result or "<empty>",
                ])
        except Exception as error:
            print("ERROR: %s" % error)
        finally:
            return ret
    steps_before, steps_after = _get_steps_for_diff(before), _get_steps_for_diff(after)
    return '\n'.join(difflib.unified_diff(steps_before, steps_after))


def all_documents(project, spaces):
    """
    Load all documents, return list
    """
    utc = pytz.UTC
    for idx, space in enumerate(spaces):
        docs = Document.get_documents(
            project, space, fields=['document_id', 'title', 'type', 'updated', 'project_id'])
        for doc in docs:
            yield {
                'space': space,
                'title': literal(doc.title),
                'type': literal(doc.type),
                'id': literal(doc.document_id),
                'project': project,
                'updated': utc.localize(doc.updated or datetime.datetime.now()),
                'workitems': doc.get_work_items(None, True, fields=['work_item_id', 'type', 'title', 'updated'])
            }


def all_workitems(doc):
    """
    Load all Workitems with given doc, return a dictionary,
    keys are workitem id, values are dicts presenting workitem attributes.
    return generator, each yield element is a dict stands for a WorkItem
    """
    utc = pytz.UTC
    space = doc['space']
    project = doc['project']
    for wi_idx, wi in enumerate(doc['workitems']):
        if wi is None or wi.title is None or wi.type is None or wi.updated is None:
            print("Invalid workitem %s" % wi)
            continue
        yield {
            'id': wi.work_item_id,
            'title': literal(wi.title),
            'type': literal(wi.type),
            'project': project,
            'space': space,
            'updated': utc.localize(wi.updated or datetime.datetime.now()),
            'document': doc
        }


def get_recent_changes(project, wi_id, service=None, start_time=None):
    """
    Get changes after start_time, return a list of dict.
    """
    def suds_2_object(suds_obj):
        dict_ = {}
        if not hasattr(suds_obj, '__dict__'):
            print("ERROR: Suds object without __dict__ attribute: {}".format(suds_obj))
        else:
            for key, value in suds_obj.__dict__.items():
                if key.startswith('_'):
                    continue
                if isinstance(value, suds.sax.text.Text):
                    value = literal(value.strip())
                elif isinstance(value, (bool, int, datetime.date, datetime.datetime)):
                    pass
                elif value is None:
                    pass
                elif isinstance(value, list):
                    value = [suds_2_object(elem) for elem in value]
                elif hasattr(value, '__dict__'):
                    value = suds_2_object(value)
                else:
                    print('Unhandled value type: %s' % type(value))
                dict_[key] = value
        return dict_
    utc = pytz.UTC
    uri = 'subterra:data-service:objects:/default/%s${WorkItem}%s' % (project, wi_id)
    service = _WorkItem.session.tracker_client.service if service is None else service
    changes = service.generateHistory(uri)
    return [suds_2_object(change) for change in changes if not start_time or utc.localize(change.date) > start_time]


def filter_step_changes(changes):
    """
    Filter out irrelevant changes, return a summary(string) of changed in diff format, and a list of authors.
    """
    summary = ""
    authors = set()
    for change in changes:
        creation = change['creation']
        date = change['date']
        diffs = change['diffs']
        empty = change['empty']
        # invalid = change['invalid']
        # revision = change['revision']
        user = change['user']

        if creation:
            summary += "User %s create this workitem at %s\n" % (user, date)
            if empty:
                continue

        if diffs:
            for diff in diffs['item']:
                before = diff.get('before', None)
                after = diff.get('after', None)
                field = diff['fieldName']

                # Ignore irrelevant properties changing
                if field not in ['testSteps']:
                    continue

                if field == 'testSteps':
                    summary += "User %s changed test steps at %s:\n%s\n" % (user, date, _diff_test_steps(before, after))
                    authors.add(user)
                    continue

                else:
                    def _get_text_content(data):
                        if not data:
                            return None
                        elif not isinstance(data, (str, unicode)):
                            if 'id' in data:  # It'a Enum?
                                data = data['id']
                            elif 'content' in data:  # It's a something else...
                                data = _convert_text(data['content'])
                            else:
                                return None
                        return data

                    before, after = _get_text_content(before), _get_text_content(after)

                    if not before or not after:
                        summary += "User %s changed %s at %s, details not avaliable.\n" % (user, field, date)
                        continue

                    else:
                        detail_diff = ''.join(difflib.unified_diff(before, after))
                        summary += "User %s changed %s at %s:\n%s\n" % (user, field, date, detail_diff)
    return summary, list(authors)


def get_automation_of_wi(project, wi_id):
    """
    Get the automation status of a workitem.
    """
    polarion_wi = _WorkItem(project_id=project, work_item_id=wi_id)
    try:
        for custom in polarion_wi._suds_object.customFields.Custom:
            if custom.key == 'caseautomation':
                return literal(custom.value.id)
    except AttributeError:
        pass
    return None


def set_automation_of_wi(project, wi_id, automation):
    """
    Get the automation status of a workitem.
    """
    polarion_wi = _WorkItem(project_id=project, work_item_id=wi_id)
    if automation not in ['manualonly', 'notautomated', 'automated']:
        raise RuntimeError("Invalud automation status: %s" % automation)
    if not _WorkItem.session.tx_in():
        _WorkItem.session.tx_begin()
    polarion_wi._set_custom_field('caseautomation', EnumOptionId(enum_id=automation)._suds_object)
    _WorkItem.session.tx_commit()
