# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
	'name': 'Customer Statement and Payments Vendor Bank Statements Reports Odoo',
	'version': '17.0.0.5',
	'category': 'Accounting',
	'summary': 'Print customer statement report print vendor statement payment reminder customer payment followup send customer statements customer account statement reports print due statement reports send due statement print supplier statement partner statement',
	'description': """
		BrowseInfo developed a new odoo/OpenERP module apps
		This module use for Print Customer Statement Print Supplier Statement Send Customer Statement by email.
		Also shows the payment followup tab which show due balance and total amount due.
		Print Customer due payment Send due payment by email Calculate due balance based on Payment Terms also send payment reminder.
		Shows partner balance customer balance partner leadger account follow-up Payment Warning Payment Reminder.
		Print Customer Statement Print Supplier Statement Send Customer Statement by email Send supplier statement by email
		Account Statement Partner statement Balance Sheet ledger Report Print Account Statement Accounting Reports Statement Reports 
		Customer report Balance Statement Customer Balance Report Customer ledger report ledger balance.
		Credit Statement Debit Statement Customer due statement Accounting Statement Creditor Reports Debtor Reports Account follow-up 
		Account followup report payment followup report payment follow-up Print Ledger report according to customer and supplier.
		Reporting function to generate statement of all transactions by partner vendor customer AR/AP for period/ All credits all debits.
		Account receivable report by period Account receivable report by customer With all transaction Credit Debit - REFER excel file Required Report AP-AR Statement for a period.
		Account Payable report by period Account Payable report by vendor WIth all transaction Credit Debit REFER excel file Required Report AP-AR Statement for a period.
		Customer statement by date So that we can see all open items in the system on that exact date REFER excel file 'Required Report' Statement of Account.
		Vendor statement by date So that we can see all open items in the system on that exact date REFER excel file 'Required Report'
		Customer statement by date So that we can see total amount for all open items in the system on that exact date only detailing GL accounts for these open items. REFER excel file required Report.
		invoice outstanding report invoice report invoice remaining amount report, invoice overdue report invoice outstanding excel report
		Vendor statement by date So that we can see total amount for all open items in the system on that exact date only detailing GL accounts for these open items. REFER excel file 'Required Report'
Openoo / OpenERP

Module use for invoice followup Account followup Payment Followup Customer followup for invoice 
	Send letter for invoice Send followup email Send email for outstading payment send email for overdue payment.
	Account follow-up management Customer follow-up management Account payment follow-up Account customer follow-up 
	follow-up payment management followup account management Outstading customer followup outstanding followup outstanding payment followup
Payment Followup payment reminder bill reminder unpaid bill followup email payment followup late invoices reminder
invoices reminder invoice reminder invoices followup Late Payment followup overdue followup Late Payment reminder
Late Payment Was Due Email Reminders for Overdue Payments late payments Email Reminders late payments for Overdue Payments Email late payments

""",
	'author': 'BrowseInfo',
	'price': 65,
	'currency': "EUR",
	'website': 'https://www.browseinfo.com',
	'depends': ['base', 'website','contacts','portal','account', 'mail'],
	
	'data': [
			'security/ir.model.access.csv',
			'report/report.xml',
			'report/customer_statement_report.xml',
			'report/overdue_report.xml',
			'report/customer_due_report.xml',
			'report/supplier_due_report.xml',
			'report/supplier_overdue_report.xml',
			'report/supplier_statement_report.xml',
			'report/filter_customer_statement_report.xml',
			'report/filter_supplier_statement_report.xml',
			'report/monthly_customer_statement_report.xml',
			'report/monthly_supplier_statement_report.xml',
			'report/weekly_customer_statement_report.xml',
			'report/weekly_supplier_statement_report.xml',
			'report/outstanding_report_wizard.xml',
			'report/report_outstanding_pdf.xml',
			'wizard/send_overdue_statement.xml',
			'views/res_partner_view.xml',
			'views/account_invoice_view.xml',
			'views/template.xml',
			'wizard/res_config_settings.xml',
			'data/account_followup_data.xml',
			'data/customer_statement_cron.xml',

	],
    'license':'OPL-1',
	'installable': True,
	'auto_install': False,
	'application': True,
	'live_test_url':'https://www.youtube.com/watch?v=NmmgHMBYNJs&feature=youtu.be',
	"images":["static/description/Banner.gif"],
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
