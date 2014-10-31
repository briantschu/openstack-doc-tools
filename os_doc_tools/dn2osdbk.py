#!/usr/bin/env python

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import argparse
import glob
import os
import re
import sys

from lxml import etree


OS_DOC_TOOLS_DIR = os.path.dirname(__file__)
DN2DBK = os.path.join(OS_DOC_TOOLS_DIR, 'resources', 'dn2osdbk.xsl')
XML_NS = '{http://www.w3.org/XML/1998/namespace}'
TRANSFORMERS = {'chapter': 'ChapterTransformer', 'book': 'BookTransformer'}


class XMLFileTransformer(object):
    """Transform a single DN XML file to docbook.

    Call the transform() method to generate the docbook output.
    """

    def __init__(self, source_file, toplevel='chapter'):
        """Initialize an instance.

        :param source_file: The path to the source DN XML file.
        :param toplevel: The top level tag of the generated docbook ('book' or
        'chapter').
        """
        self.source_file = source_file
        self.toplevel = toplevel
        basename = os.path.basename(self.source_file)
        self.basename = os.path.splitext(basename)[0]
        self.xslt_file = DN2DBK

    def _xslt_transform(self, xml):
        with open(self.xslt_file) as fd:
            xslt = fd.read()
        xslt_root = etree.XML(xslt)
        transform = etree.XSLT(xslt_root)
        return transform(xml)

    def _custom_transform(self, tree):
        # Set the correct root tag
        root = tree.getroot()
        root.tag = '{http://docbook.org/ns/docbook}%s' % self.toplevel

        # Add a comment to warn that the file is autogenerated
        comment = etree.Comment("WARNING: This file is automatically "
                                "generated. Do not edit it.")
        root.insert(0, comment)

        for item in tree.iter():
            # Find tags with an 'id' attribute. In case there are multiple
            # space-separated IDs, we have to make a choice.
            id_attrib = '%sid' % XML_NS
            xml_id = item.get(id_attrib)
            if xml_id is not None:
                id_list = xml_id.split(' ')
                # If the title and an associated reference target match, sphinx
                # generates a second id like 'id[0-9]' which is hardly usable.
                # So we take the first id in that case, otherwise the last.
                if len(id_list) > 1 and re.match(r'id\d+', id_list[-1]):
                    xml_id = id_list[0]
                else:
                    xml_id = id_list[-1]

                item.attrib[id_attrib] = xml_id

        return tree

    def transform(self):
        """Generate the docbook XML."""
        with open(self.source_file) as fd:
            source_xml = fd.read()

        source_doc = etree.XML(source_xml)
        result_tree = self._xslt_transform(source_doc)
        result_tree = self._custom_transform(result_tree)
        return etree.tostring(result_tree, pretty_print=True,
                              xml_declaration=True, encoding="UTF-8")


class BaseFolderTransformer(object):
    """Base class for generating docbook from an DN XML source dir."""
    file_toplevel = 'section'

    def __init__(self, source_dir, output_dir, index='index.xml'):
        """Initialize an instance.

        :param source_dir: The DN XML source directory.
        :param output_dir: The directory in which docbook files will be stored.
        This directory is created if it doesn't exist.
        :param index: The name of the index file in the source dir.
        """
        self.source_dir = source_dir
        self.output_dir = output_dir
        self.index = index
        self.includes = []
        self.title = None

        self.parse_index()

        if not os.path.isdir(self.output_dir):
            os.makedirs(self.output_dir)

    def parse_index(self):
        """Generates part of the docbook index from the DN XML index.

        The full index is generated in the write_index method.
        """
        src = os.path.join(self.source_dir, 'index.xml')
        src_xml = etree.XML(open(src).read())
        for reference in src_xml.iter('reference'):
            if '#' in reference.get('refuri'):
                continue

            self.includes.append("%s_%s.xml" % (self.file_toplevel,
                                                reference.get('refuri')))

        self.title = src_xml.find('section/title').text

    def write_index(self):
        """Write the index file.

        This method must be implemented by subclasses.
        """
        raise NotImplementedError

    def transform(self):
        """Perform the actual conversion."""
        files = glob.glob(os.path.join(self.source_dir, '*.xml'))
        for src in files:
            if src.endswith('/index.xml'):
                continue
            basename = '%s_%s' % (self.file_toplevel, os.path.basename(src))
            output_file = os.path.join(self.output_dir, basename)
            transformer = XMLFileTransformer(src, self.file_toplevel)
            xml = transformer.transform()
            open(output_file, 'w').write(xml)
        self.write_index()


class BookTransformer(BaseFolderTransformer):
    """Create a docbook book."""
    file_toplevel = 'chapter'

    def write_index(self):
        output_file = os.path.join(self.output_dir, 'index.xml')
        xml_id = self.title.lower().replace(' ', '-')
        includes = "\n    ".join([
            '<xi:include href="%s"/>' % i for i in self.includes])

        output = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE book [
]>
<book xmlns="http://docbook.org/ns/docbook"
  xmlns:xi="http://www.w3.org/2001/XInclude"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  version="5.0"
  xml:id="%(xml_id)s">

    <!-- WARNING: This file is automatically generated. Do not edit it. -->

    <title>%(title)s</title>
    %(includes)s
</book>
''' % {'xml_id': xml_id, 'title': self.title, 'includes': includes}

        open(output_file, 'w').write(output)


class ChapterTransformer(BaseFolderTransformer):
    """Create a docbook chapter."""
    file_toplevel = 'section'

    def write_index(self):
        output_file = os.path.join(self.output_dir, 'index.xml')
        xml_id = self.title.lower().replace(' ', '-')
        includes = "\n    ".join([
            '<xi:include href="%s"/>' % i for i in self.includes])

        output = '''<?xml version="1.0" encoding="UTF-8"?>
<chapter xmlns="http://docbook.org/ns/docbook"
  xmlns:xi="http://www.w3.org/2001/XInclude"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  version="5.0"
  xml:id="%(xml_id)s">

    <!-- WARNING: This file is automatically generated. Do not edit it. -->

    <title>%(title)</title>
    %(includes)s
</chapter>
''' % {'xml_id': xml_id, 'title': self.title, 'includes': includes}

        open(output_file, 'w').write(output)


def main():
    parser = argparse.ArgumentParser(description="Generate docbook from "
                                     "DocUtils Native XML format")
    parser.add_argument('source', help='Source file or directory.')
    parser.add_argument('output', help='Output file or directory.')
    parser.add_argument('--toplevel', help='Toplevel flag.',
                        choices=['book', 'chapter'],
                        default='chapter')
    args = parser.parse_args()

    if os.path.isdir(args.source):
        cls = globals()[TRANSFORMERS[args.toplevel]]
        transformer = cls(args.source, args.output)
        sys.exit(transformer.transform())
    else:
        transformer = XMLFileTransformer(args.source, args.toplevel)
        xml = transformer.transform()
        with open(args.output, 'w') as fd:
            fd.write(xml)
        sys.exit(0)


if __name__ == "__main__":
        main()
