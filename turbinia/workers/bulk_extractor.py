# -*- coding: utf-8 -*-
# Copyright 2019 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Task for running Bulk Extractor."""

import os
import logging
import xml.etree.ElementTree as xml_tree

from turbinia import TurbiniaException

from turbinia.evidence import BulkExtractorOutput
from turbinia.workers import TurbiniaTask
from turbinia.lib import text_formatter as fmt

log = logging.getLogger('turbinia')


class BulkExtractorTask(TurbiniaTask):
  """Task to generate Bulk Extractor output."""

  def run(self, evidence, result):
    """Run Bulk Extractor binary.

    Args:
        evidence (Evidence object): The evidence we will process.
        result (TurbiniaTaskResult): The object to place task results into.

    Returns:
        TurbiniaTaskResult object.
    """
    # TODO(wyassine): Research whether bulk extractor has an option to
    # generate a summary report to stdout so that it could be used for
    # a report in this task.
    # Create the new Evidence object that will be generated by this Task.
    output_evidence = BulkExtractorOutput()
    # Create a path that we can write the new file to.
    base_name = os.path.basename(evidence.local_path)
    output_file_path = os.path.join(self.output_dir, base_name)
    # Add the output path to the evidence so we can automatically save it
    # later.
    output_evidence.local_path = output_file_path

    try:
      # Generate the command we want to run then execute.
      cmd = 'bulk_extractor {0:s} -o {1:s}'.format(
          evidence.local_path, output_file_path)
      result.log('Running Bulk Extractor as [{0:s}]'.format(cmd))
      self.execute(cmd, result, new_evidence=[output_evidence], shell=True)

      # Generate bulk extractor report
      (report, summary) = self.generate_summary_report(output_file_path)
      output_evidence.text_data = report
      result.report_data = output_evidence.text_data

      # Compress the bulk extractor output directory.
      output_evidence.compress()
      result.close(self, success=True, status=summary)
    except TurbiniaException as exception:
      result.close(self, success=False, status=str(exception))
      return result
    return result

  def generate_summary_report(self, output_file_path):
    """Generate a summary report from the resulting bulk extractor run.

    Args:
      output_file_path(str): the path to the bulk extractor output.

    Returns:
      tuple: containing:
        report_test(str): The report data
        summary(str): A summary of the report (used for task status)
    """
    findings = []
    features_count = 0
    report_path = os.path.join(output_file_path, 'report.xml')

    # Check if report.xml was not generated by bulk extractor.
    if not os.path.exists(report_path):
      report = 'Execution successful, but the report is not available.'
      return (report, report)

    # Parse existing XML file.
    xml = xml_tree.parse(report_path)

    # Place in try/except statement to continue execution when
    # an attribute is not found and NoneType is returned.
    try:
      # Retrieve summary related results.
      findings.append(fmt.heading4('Bulk Extractor Results'))
      findings.append(fmt.heading5('Run Summary'))
      findings.append(
          fmt.bullet(
              'Program: {0} - {1}'.format(
                  xml.find('creator/program').text,
                  xml.find('creator/version').text)))
      findings.append(
          fmt.bullet(
              'Command Line: {0}'.format(
                  xml.find('creator/execution_environment/command_line').text)))
      findings.append(
          fmt.bullet(
              'Start Time: {0}'.format(
                  xml.find('creator/execution_environment/start_time').text)))
      findings.append(
          fmt.bullet(
              'Elapsed Time: {0}'.format(
                  xml.find('report/elapsed_seconds').text)))

      # Retrieve results from each of the scanner runs
      feature_files = xml.find('feature_files')
      if feature_files is not None:
        feature_iter = feature_files.iter()
        findings.append(fmt.heading5('Scanner Results'))
        for f in feature_iter:
          if f.tag == 'feature_file':
            name = next(feature_iter)
            count = next(feature_iter)
            findings.append(fmt.bullet('{0}:{1}'.format(name.text, count.text)))
            features_count += int(count.text)
      else:
        findings.append(fmt.heading5("There are no findings to report."))
    except AttributeError as exception:
      log.warning(
          'Error parsing feature from Bulk Extractor report: {0!s}'.format(
              exception))
    summary = '{0} artifacts have been extracted.'.format(features_count)
    report = '\n'.join(findings)
    return (report, summary)