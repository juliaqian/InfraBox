#pylint: disable=too-few-public-methods
import uuid
import json
import os
import xml.etree.ElementTree

class File(object):
    def __init__(self, name):
        self.name = name
        self.functions_found = 0
        self.functions_hit = 0
        self.branches_found = 0
        self.branches_hit = 0
        self.lines_hit = 0
        self.lines_found = 0

class Parser(object):
    def __init__(self, i):
        self.input = i
        self.files = []

    def __convert_clover_xml(self):
        e = xml.etree.ElementTree.parse(self.input).getroot()
        data = e.findall('./project/metrics/file')

        for d in data:
            print d
            f = File(d.get('name'))
            metrics = d.find('metrics')

            f.functions_found = int(metrics.get('methods', 0))
            f.functions_hit = int(metrics.get('coveredmethods', 0))
            f.branches_found = int(metrics.get('conditionals', 0))
            f.branches_hit = int(metrics.get('coveredconditionals', 0))
            f.lines_found = int(metrics.get('statements', 0))
            f.lines_hit = int(metrics.get('coveredstatements', 0))

            self.files.append(f)


    def __convert_xml(self):
        root = xml.etree.ElementTree.parse(self.input).getroot()

        data = root.get('clover', None)
        if data:
            self.__convert_clover_xml()
            return

        data = root.findall('.//packages//class//lines')
        if data:
            self.__convert_cobertura()
            return

        raise Exception('Could not detect coverage format')

    def __convert_cobertura(self):
        e = xml.etree.ElementTree.parse(self.input).getroot()

        for c in e.findall('.//class'):
            lines = c.findall('.//line')
            f = File(c.get('filename'))

            branches_count = 0
            branches_missing = 0
            branches_partial = 0
            statements_count = len(lines)
            statements_missing = 0

            for l in lines:
                is_branch = l.get("branch", False)
                is_branch = is_branch in (True, 'true', 'True')

                if is_branch:
                    cc = l.get("condition-coverage")
                    cc = cc[cc.find("(")+1:cc.find(")")]
                    cc = cc.split("/")

                    if int(cc[0]) > 0:
                        branches_partial += int(cc[1]) - int(cc[0])
                    else:
                        branches_missing += int(cc[1]) - int(cc[0])

                    branches_count += int(cc[1])

                hits = int(l.get('hits', 0))
                if hits == 0:
                    statements_missing += 1

            f.branches_found = branches_count
            f.branches_hit = branches_count - branches_missing
            f.lines_found = statements_count
            f.lines_hit = statements_count - statements_missing

            self.files.append(f)


    def __convert_lcov(self):
        with open(self.input) as i:
            content = i.readlines()
            content = [x.strip() for x in content]

        f = None
        for l in content:
            if l.startswith("SF:"):
                f = File(l[3:-1])
            elif l.startswith("FNF:"):
                f.functions_found = int(l[4:])
            elif l.startswith("FNH:"):
                f.functions_hit = int(l[4:])
            elif l.startswith("BRF:"):
                f.branches_found = int(l[4:])
            elif l.startswith("BRH:"):
                f.branches_hit = int(l[4:])
            elif l.startswith("LH:"):
                f.lines_hit = int(l[3:])
            elif l.startswith("LF:"):
                f.lines_found = int(l[3:])
            elif l == "end_of_record":
                self.files.append(f)

    def __create_markup(self, badge_dir):
        functions_found = 0
        functions_hit = 0
        branches_found = 0
        branches_hit = 0
        lines_found = 0
        lines_hit = 0

        for f in self.files:
            functions_found += f.functions_found
            functions_hit += f.functions_hit
            branches_found += f.branches_found
            branches_hit += f.branches_hit
            lines_found += f.lines_found
            lines_hit += f.lines_hit

        found = functions_found + branches_found + lines_found
        hit = functions_hit + branches_hit + lines_hit
        cov = 0
        if found > 0:
            cov = int((hit / float(found)) * 100)

        rows = []
        for f in self.files:
            branches_cov = 0
            lines_cov = 0
            functions_cov = 0

            if f.branches_found > 0:
                branches_cov = int((f.branches_hit / float(f.branches_found) * 100.0))

            if f.functions_found > 0:
                functions_cov = int((f.functions_hit / float(f.functions_found) * 100.0))

            if f.lines_found > 0:
                lines_cov = int((f.lines_hit / float(f.lines_found) * 100.0))

            rows.append([{
                "type": "text",
                "text": f.name
            }, {
                "type": "text",
                "text": "%s%%" % branches_cov
            }, {
                "type": "text",
                "text": "%s/%s" % (f.branches_hit, f.branches_found)
            }, {
                "type": "text",
                "text": "%s%%" % functions_cov
            }, {
                "type": "text",
                "text": "%s/%s" % (f.functions_hit, f.functions_found)
            }, {
                "type": "text",
                "text": "%s%%" %  lines_cov
            }, {
                "type": "text",
                "text": "%s/%s" % (f.lines_hit, f.lines_found)
            }])


        # Headline
        elements = []
        elements.append({
            "type": "h1",
            "text": "Coverage Report: %s%%" % cov
        })

        headers = [{
            "type": "text",
            "text": "File"
        }, {
            "type": "text",
            "text": "Branches"
        }, {
            "type": "text",
            "text": " "
        }, {
            "type": "text",
            "text": "Functions"
        }, {
            "type": "text",
            "text": " "
        }, {
            "type": "text",
            "text": "Lines"
        }, {
            "type": "text",
            "text": " "
        }]

        elements.append({
            "type": "table",
            "headers": headers,
            "rows": rows
        })

        doc = {
            "version": 1,
            "title": "Code Coverage",
            "elements": elements
        }

        badge_path = os.path.join(badge_dir, "%s.json" % str(uuid.uuid4()))
        json.dump({
            "version": 1,
            "subject": "coverage",
            "status": "%s %%" % cov,
            "color": "green"
        }, open(badge_path, 'w+'), indent=4)

        return doc

    def parse(self, badge_dir):
        self.__convert_xml()
        return self.__create_markup(badge_dir)
