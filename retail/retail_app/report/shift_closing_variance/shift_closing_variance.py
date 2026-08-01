from retail.retail_app.report.pos_report_utils import execute_report


def execute(filters=None):
	return execute_report("Shift Closing Variance", filters)
