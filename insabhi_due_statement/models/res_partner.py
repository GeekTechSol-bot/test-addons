# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
##############################################################################
from odoo import api, fields, models, _
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
import base64


class Res_Partner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def default_get(self, fields):
        res = super(Res_Partner, self).default_get(fields)
        if 'parent_id' in fields and res.get('parent_id'):
            parent = self.browse(res.get('parent_id'))
            res['company_id'] = parent.company_id.id
        else:
            if 'allowed_company_ids' in self.env.context:
                res['company_id'] = self.env.context['allowed_company_ids'][0]
        return res

    def _get_amounts_and_date_amount(self):
        user_id = self._uid
        filter_amount_due = 0.0
        filter_amount_overdue = 0.0
        filter_supplier_amount_due = 0.0
        filter_supplier_amount_overdue = 0.0

        company = self.env['res.users'].browse(user_id).company_id
        current_date = fields.Date.today()
        for partner in self:
            if partner.company_id.send_statement and partner.company_id.auto_weekly_statement:
                partner.do_process_weekly_statement_filter()
            if partner.company_id.send_statement and partner.company_id.auto_monthly_statement:
                partner.do_process_monthly_statement_filter()
            if partner.company_id.supplier_statement and partner.company_id.sup_auto_weekly_statement:
                partner.do_process_supplier_weekly_statement_filter()
            if partner.company_id.supplier_statement and partner.company_id.sup_auto_monthly_statement:
                partner.do_process_supplier_monthly_statement_filter()

            filter_date = current_date
            supp_filter_date = current_date

            if partner.statement_to_date:
                filter_date = partner.statement_to_date

            if partner.vendor_statement_to_date:
                supp_filter_date = partner.vendor_statement_to_date

            amount_due = amount_overdue = 0.0
            supplier_amount_due = supplier_amount_overdue = 0.0

            for aml in partner.balance_invoice_ids:
                if aml.company_id == partner.env.company:
                    date_maturity = aml.invoice_date_due or aml.date
                    amount_due += aml.result
                    if date_maturity:
                        if date_maturity <= current_date:
                            amount_overdue += aml.result

            partner.payment_amount_due_amt = amount_due
            partner.payment_amount_overdue_amt = amount_overdue

            for aml in partner.supplier_invoice_ids:
                date_maturity = aml.invoice_date_due or aml.date
                supplier_amount_due += aml.result
                if date_maturity:
                    if date_maturity <= current_date:
                        supplier_amount_overdue += aml.result
            partner.payment_amount_due_amt_supplier = supplier_amount_due
            partner.payment_amount_overdue_amt_supplier = supplier_amount_overdue

            for aml in partner.customer_statement_line_ids:
                if aml.invoice_date_due != False:
                    date_maturity = aml.invoice_date_due
                    filter_amount_due += aml.result
                    if date_maturity:
                        if date_maturity <= filter_date:
                            filter_amount_overdue += aml.result
            partner.filter_payment_amount_due_amt = filter_amount_due
            partner.filter_payment_amount_overdue_amt = filter_amount_overdue

            for aml in partner.vendor_statement_line_ids:
                date_maturity = aml.invoice_date_due
                filter_supplier_amount_due += aml.result
                if date_maturity:
                    if date_maturity <= supp_filter_date:
                        filter_supplier_amount_overdue += aml.result
            partner.filter_payment_amount_due_amt_supplier = filter_supplier_amount_due
            partner.filter_payment_amount_overdue_amt_supplier = filter_supplier_amount_overdue

            monthly_amount_due_amt = monthly_amount_overdue_amt = 0.0
            for aml in partner.monthly_statement_line_ids:
                if aml.invoice_type == 'invoice':
                    date_maturity = aml.invoice_date_due
                    monthly_amount_due_amt += aml.result
                    if date_maturity:
                        if date_maturity <= current_date:
                            monthly_amount_overdue_amt += aml.result
                partner.monthly_payment_amount_due_amt = monthly_amount_due_amt
                partner.monthly_payment_amount_overdue_amt = monthly_amount_overdue_amt

            sup_monthly_amount_due_amt = sup_monthly_amount_overdue_amt = 0.0
            for aml in partner.monthly_statement_line_ids:
                if aml.invoice_type == 'bill':
                    date_maturity = aml.invoice_date_due
                    sup_monthly_amount_due_amt += aml.result
                    if date_maturity:
                        if date_maturity <= current_date:
                            sup_monthly_amount_overdue_amt += aml.result
                partner.sup_monthly_payment_amount_due_amt = sup_monthly_amount_due_amt
                partner.sup_monthly_payment_amount_overdue_amt = sup_monthly_amount_overdue_amt

            weekly_amount_due_amt = weekly_amount_overdue_amt = 0.0
            for aml in partner.weekly_statement_line_ids:
                if aml.invoice_type == 'invoice':
                    date_maturity = aml.invoice_date_due
                    weekly_amount_due_amt += aml.result
                    if date_maturity:
                        if date_maturity <= current_date:
                            weekly_amount_overdue_amt += aml.result
                partner.weekly_payment_amount_due_amt = weekly_amount_due_amt
                partner.weekly_payment_amount_overdue_amt = weekly_amount_overdue_amt

            sup_weekly_payment_amount_due_amt = 0.0
            sup_weekly_amount_overdue_amt = 0.0
            for aml in partner.weekly_statement_line_ids:
                if aml.invoice_type == 'bill':
                    date_maturity = aml.invoice_date_due
                    sup_weekly_payment_amount_due_amt += aml.result
                    if date_maturity:
                        if date_maturity <= current_date:
                            sup_weekly_amount_overdue_amt += aml.result
                partner.sup_weekly_payment_amount_due_amt = sup_weekly_payment_amount_due_amt
                partner.sup_weekly_payment_amount_overdue_amt = sup_weekly_amount_overdue_amt

    @api.depends('customer_statement_line_ids')
    def compute_days_filter(self):
        today = fields.date.today()
        for partner in self:
            partner.first_thirty_day_filter = 0
            partner.thirty_sixty_days_filter = 0
            partner.sixty_ninty_days_filter = 0
            partner.ninty_plus_days_filter = 0
            from_date = partner.statement_from_date
            to_date = partner.statement_to_date
            move_line = self.env['account.move.line']
            domain = [('account_id.account_type', '=', 'asset_receivable'), ('partner_id', '=', partner.id),
                      ('move_id.state', 'in', ['posted'])]
            if from_date:
                domain.append(('date_maturity', '>=', from_date))

            if to_date:
                domain.append(('date_maturity', '<=', to_date))

            for ml in move_line.search(domain):
                if to_date and ml.date_maturity:
                    diff = to_date - ml.date_maturity
                elif ml.date_maturity:
                    diff = fields.date.today() - ml.date_maturity
                else:
                    diff = fields.date.today() - fields.date.today()

                if diff.days >= 0 and diff.days <= 30:
                    partner.first_thirty_day_filter = partner.first_thirty_day_filter + ml.amount_residual

                elif diff.days > 30 and diff.days <= 60:
                    partner.thirty_sixty_days_filter = partner.thirty_sixty_days_filter + ml.amount_residual

                elif diff.days > 60 and diff.days <= 90:
                    partner.sixty_ninty_days_filter = partner.sixty_ninty_days_filter + ml.amount_residual
                else:
                    if diff.days > 90:
                        partner.ninty_plus_days_filter = partner.ninty_plus_days_filter + ml.amount_residual
        return

    def compute_days(self):
        today = fields.date.today()
        for partner in self:
            partner.first_thirty_day = 0
            partner.thirty_sixty_days = 0
            partner.sixty_ninty_days = 0
            partner.ninty_plus_days = 0

            moves = self.env['account.move'].search([('partner_id', '=', partner.id), ('state', 'in', ['posted'])])
            for mv in moves:
                for ml in mv.line_ids:
                    if ml.account_id.account_type == 'asset_receivable':
                        if ml.date_maturity:
                            diff = today - ml.date_maturity
                        else:
                            diff = today - today
                        if diff.days >= 0 and diff.days <= 30:
                            partner.first_thirty_day = partner.first_thirty_day + ml.amount_residual

                        elif diff.days > 30 and diff.days <= 60:
                            partner.thirty_sixty_days = partner.thirty_sixty_days + ml.amount_residual

                        elif diff.days > 60 and diff.days <= 90:
                            partner.sixty_ninty_days = partner.sixty_ninty_days + ml.amount_residual
                        else:
                            if diff.days > 90:
                                partner.ninty_plus_days = partner.ninty_plus_days + ml.amount_residual
        return

    def compute_days_custom(self):
        today = fields.date.today()
        for partner in self:
            partner.first_thirty_days_custom = 0
            partner.thirty_sixty_days_custom = 0
            partner.sixty_ninty_days_custom = 0
            partner.ninty_plus_days_custom = 0

            moves = self.env['account.move'].search([('partner_id', '=', partner.id), ('state', 'in', ['posted'])])
            domain = [('account_id.account_type', '=', 'asset_receivable'), ('partner_id', '=', partner.id)]

            for mv in moves:
                for ml in mv.line_ids:
                    if ml.account_id.account_type == 'asset_receivable':
                        if self.custom_from_date and self.custom_to_date and ml.date_maturity:
                            if ml.date_maturity >= self.custom_from_date and ml.date_maturity <= self.custom_to_date:
                                if ml.account_id.account_type == 'asset_receivable':
                                    if ml.date_maturity:
                                        diff = today - ml.date_maturity
                                    else:
                                        diff = today - today
                                    if diff.days >= 0 and diff.days <= 30:
                                        partner.first_thirty_days_custom = partner.first_thirty_days_custom + ml.amount_residual
                                    elif diff.days > 30 and diff.days <= 60:
                                        partner.thirty_sixty_days_custom = partner.thirty_sixty_days_custom + ml.amount_residual

                                    elif diff.days > 60 and diff.days <= 90:
                                        partner.sixty_ninty_days_custom = partner.sixty_ninty_days_custom + ml.amount_residual
                                    else:
                                        if diff.days > 90:
                                            partner.ninty_plus_days_custom = partner.ninty_plus_days_custom + ml.amount_residual
        return

    @api.depends('ninty_plus_days', 'sixty_ninty_days', 'thirty_sixty_days', 'first_thirty_day')
    def compute_total(self):
        for partner in self:
            partner.total = 0.0
            partner.total = partner.ninty_plus_days + partner.sixty_ninty_days + partner.thirty_sixty_days + partner.first_thirty_day
        return

    @api.depends('ninty_plus_days_custom', 'sixty_ninty_days_custom', 'thirty_sixty_days_custom',
                 'first_thirty_days_custom')
    def compute_total_custom(self):
        for partner in self:
            partner.custom_total = 0.0
            partner.custom_total = partner.ninty_plus_days_custom + partner.sixty_ninty_days_custom + partner.thirty_sixty_days_custom + partner.first_thirty_days_custom
        return

    @api.depends('ninty_plus_days_filter', 'sixty_ninty_days_filter', 'thirty_sixty_days_filter',
                 'first_thirty_day_filter')
    def compute_total_filter(self):
        for partner in self:
            partner.total_filter = 0.0
            partner.total_filter = partner.ninty_plus_days_filter + partner.sixty_ninty_days_filter + partner.thirty_sixty_days_filter + partner.first_thirty_day_filter
        return

    is_set_statments = fields.Boolean(string='Set Staments', compute='_compute_set_statments', default=False)
    supplier_invoice_ids = fields.One2many('account.move', 'partner_id', 'Supplier move lines',
                                           domain=[('move_type', 'in', ['in_invoice', 'in_refund', 'entry']),
                                                   ('state', 'in', ['posted']), ('is_set_statments', '=', True)])
    balance_invoice_ids = fields.One2many('account.move', 'partner_id', 'Customer move lines',
                                          domain=[('move_type', 'in', ['out_invoice', 'out_refund', 'entry']),
                                                  ('state', 'in', ['posted']), ('is_set_statments', '=', True)])

    monthly_statement_line_ids = fields.One2many('monthly.statement.line', 'partner_id', 'Monthly Statement Lines')
    weekly_statement_line_ids = fields.One2many('weekly.statement.line', 'partner_id', 'Weekly Statement Lines')

    customer_statement_line_ids = fields.One2many('bi.statement.line', 'partner_id', 'Customer Statement Lines')
    vendor_statement_line_ids = fields.One2many('bi.vendor.statement.line', 'partner_id', 'Supplier Statement Lines')
    custom_statement_line_ids = fields.One2many('custom.statement.line', 'partner_id', 'Custom Statement Lines')

    payment_amount_due_amt = fields.Float(compute='_get_amounts_and_date_amount', string="Balance Due", store=True)
    payment_amount_overdue_amt = fields.Float(compute='_get_amounts_and_date_amount',
                                              string="Total Overdue Amount", store=True)
    payment_amount_due_amt_supplier = fields.Float(compute='_get_amounts_and_date_amount',
                                                   string="Supplier Balance Due", store=True)
    payment_amount_overdue_amt_supplier = fields.Float(compute='_get_amounts_and_date_amount',
                                                       string="Total Supplier Overdue Amount", store=True)
    filter_payment_amount_due_amt = fields.Float(compute='_get_amounts_and_date_amount', string="Filter Balance Due",
                                                 store=True)
    filter_payment_amount_overdue_amt = fields.Float(compute='_get_amounts_and_date_amount',
                                                     string="Filter Total Overdue Amount", store=True)
    monthly_payment_amount_due_amt = fields.Monetary(compute='_get_amounts_and_date_amount',
                                                     string=" Filter Monthly Balance Due", store=True)
    monthly_payment_amount_overdue_amt = fields.Float(compute='_get_amounts_and_date_amount',
                                                      string="Filter Total Monthly Overdue Amount", store=True)

    sup_monthly_payment_amount_due_amt = fields.Float(compute='_get_amounts_and_date_amount',
                                                      string=" Filter Supplier Monthly Balance Due", store=True)
    sup_monthly_payment_amount_overdue_amt = fields.Float(compute='_get_amounts_and_date_amount',
                                                          string="Filter Supplier Total Monthly Overdue Amount",
                                                          store=True)

    weekly_payment_amount_due_amt = fields.Float(compute='_get_amounts_and_date_amount',
                                                 string="Filter Weekly Balance Due", store=True)
    weekly_payment_amount_overdue_amt = fields.Float(compute='_get_amounts_and_date_amount',
                                                     string="Filter Weekly Total Overdue Amount", store=True)

    sup_weekly_payment_amount_due_amt = fields.Float(compute='_get_amounts_and_date_amount',
                                                     string="Filter Supplier Weekly Balance Due", store=True)
    sup_weekly_payment_amount_overdue_amt = fields.Float(compute='_get_amounts_and_date_amount',
                                                         string="Filter Supplier Weekly Total Overdue Amount",
                                                         store=True)

    filter_payment_amount_due_amt_supplier = fields.Float(compute='_get_amounts_and_date_amount',
                                                          string="Filter Supplier Balance Due", store=True)
    filter_payment_amount_overdue_amt_supplier = fields.Float(compute='_get_amounts_and_date_amount',
                                                              string="Filter Total Supplier Overdue Amount", store=True)
    first_thirty_days_custom = fields.Float(string="0-30 custom", compute="compute_days_custom")
    thirty_sixty_days_custom = fields.Float(string="30-60 custom", compute="compute_days_custom")
    sixty_ninty_days_custom = fields.Float(string="60-90 custom", compute="compute_days_custom")
    ninty_plus_days_custom = fields.Float(string="90+ custom", compute="compute_days_custom")
    custom_total = fields.Float(string="Total custom", compute="compute_total_custom")

    first_thirty_day = fields.Float(string="0-30", compute="compute_days")
    thirty_sixty_days = fields.Float(string="30-60", compute="compute_days")
    sixty_ninty_days = fields.Float(string="60-90", compute="compute_days")
    ninty_plus_days = fields.Float(string="90+", compute="compute_days")
    total = fields.Float(string="Total", compute="compute_total")
    first_thirty_day_filter = fields.Float(string="0-30 filter", compute="compute_days_filter")
    thirty_sixty_days_filter = fields.Float(string="30-60 filter", compute="compute_days_filter")
    sixty_ninty_days_filter = fields.Float(string="60-90 filter", compute="compute_days_filter")
    ninty_plus_days_filter = fields.Float(string="90+ filter", compute="compute_days_filter")
    total_filter = fields.Float(string="Filter Total", compute="compute_total_filter")

    statement_from_date = fields.Date('From Date')
    statement_to_date = fields.Date('To Date')
    custom_from_date = fields.Date('Custom From Date')
    custom_to_date = fields.Date('Custom To Date')

    today_date = fields.Date(default=fields.Date.today())
    vendor_statement_from_date = fields.Date('Supplier From Date')
    vendor_statement_to_date = fields.Date('Supplier To Date')

    initial_bal = fields.Float(string='Initial Balance', readonly=True)
    initial_supp_bal = fields.Float(string='Initial Supplier Balance', readonly=True)
    # opt_statement = fields.Boolean('Opt Statement', default=False)
    statments = fields.Selection(related='company_id.statments', string="Statements", readonly=False)
    opening_balance = fields.Float(string='Opening Balance', readonly=True)
    vendor_opening_balance = fields.Float(string="Vendor Opening Balance", readonly=True)
    filter_selection = fields.Selection([('all', 'Full Statement'), ('due', 'Due')], default='all', string='Filter By')
    hide_statement = fields.Selection(
        [('hide_vendor_statement', 'Hide Vendor Statement'), ('hide_customer_statement', 'Hide Customer Statement'),
         ('hide_both', 'Hide Both')], default='hide_both', compute='_compute_hide_statement', store=True)
    date_selection = fields.Selection(
        selection=[('7', '7 Days'), ('14', '14 Days'), ('21', '21 Days'), ('30', '30 Days')],
        string="Reminder Interval",
    )
    next_sent_date = fields.Date(
        string="Next Sent Date",
        default=fields.Date.today()
    )
    customer_statements = fields.Boolean(string="Customer Statements")
    customer_due_payments = fields.Boolean(string="Customer Due Payments")
    vendor_payment = fields.Boolean(string="Vendor Payment")
    vendor_due_payments = fields.Boolean(string="Vendor Due Payments")

    @api.onchange('date_selection')
    def _onchange_date_selection(self):
        """Update the start date based on the selected interval."""
        send_date = self.next_sent_date or date.today()
        if self.date_selection:
            self.next_sent_date = send_date + timedelta(days=int(self.date_selection))

    @api.model
    def _send_report_emails(self):
        """Scheduled action to send reminder emails."""
        partners = self.search([
            ('date_selection', '!=', False),
            ('next_sent_date', '=', date.today()),
        ])
        for partner in partners:
            self.send_email_report(partner)
            reminder_days = int(partner.date_selection)
            partner.next_sent_date += timedelta(days=reminder_days)

    def send_email_report(self, partner):
        """Send email with reports based on selected options."""
        customer_reports = []
        vendor_reports = []

        if partner.customer_statements:
            customer_reports.append(self._generate_customer_statement_report(partner))
        if partner.customer_due_payments:
            customer_reports.append(self._generate_customer_due_payment_report(partner))
        if partner.vendor_due_payments:
            vendor_reports.append(self._generate_vendor_due_payment_report(partner))
        if partner.vendor_payment:
            vendor_reports.append(self._generate_vendor_statement_report(partner))

        company_name = self.env.user.company_id.name or ''
        company = self.env.user.company_id

        if customer_reports:
            attachment_ids = [report.id for report in customer_reports if hasattr(report, 'id')]
            if attachment_ids:
                customer_statement = company.customer_statement or f"""
                                              <div style="font-family: 'Lucica Grande', Ubuntu, Arial, Verdana, sans-serif; font-size: 12px; color: rgb(34, 34, 34); background-color: rgb(255, 255, 255);">
                                                  <p>Dear {partner.name or ''},</p>
                                                  <p>We have attached your payment statement. Please kindly check.</p>
                                                  <br/>
                                                  Best Regards,<br/>
                                                  <br/>
                                                  {company_name}
                                              </div>
                                              """
                mail_values = {
                    'subject': f'{company_name} Customer Statement',
                    'body_html':customer_statement ,
                    'email_to': partner.email,
                    'email_from': self.env.user.email or self.env.company.email,
                    'attachment_ids': [(6, 0, attachment_ids)],
                }
                customer_mail = self.env['mail.mail'].create(mail_values)
                customer_mail.send()
                self.env['email.log'].create({
                    'partner_id': partner.id,
                    'email_from': company.email,
                    'email_to': partner.email,
                    'statement_type': f'{company_name} Customer Statement',
                    'status': 'sent'
                })

        if vendor_reports:
            attachment_ids = [report.id for report in vendor_reports if hasattr(report, 'id')]
            if attachment_ids:
                vendor_body = company.vendor_statement or f"""
                               <div style="font-family: 'Lucica Grande', Ubuntu, Arial, Verdana, sans-serif; font-size: 12px; color: rgb(34, 34, 34); background-color: rgb(255, 255, 255);">
                                   <p>Dear {partner.name or ''},</p>
                                   <p>We have attached your payment statement. Please kindly check.</p>
                                   <br/>
                                   Best Regards,<br/>
                                   <br/>
                                   {company_name}
                               </div>
                               """
                mail_values = {
                    'subject': f'{company_name} Supplier Statement',
                    'body_html': vendor_body,
                    'email_to': partner.email,
                    'email_from': self.env.user.email or self.env.company.email,
                    'attachment_ids': [(6, 0, attachment_ids)],
                }
                vendor_mail = self.env['mail.mail'].create(mail_values)
                vendor_mail.send()
                self.env['email.log'].create({
                    'partner_id': partner.id,
                    'email_from': company.email,
                    'email_to': partner.email,
                    'statement_type': f'{company_name} Supplier Statement',
                    'status': 'sent'
                })

    def _generate_customer_statement_report(self, partner):
        ir_actions_report_sudo = self.env['ir.actions.report'].sudo()
        statement_report_action = self.env.ref('insabhi_due_statement.report_customert_print')
        attachment_id = False
        for statement in partner:
            statement_report = statement_report_action.sudo()
            content, _content_type = ir_actions_report_sudo._render_qweb_pdf(statement_report, res_ids=statement.ids)
            attachment_id = self.env['ir.attachment'].create({
                'name': f"Customer Statement - {partner.name}.pdf",
                'type': 'binary',
                'mimetype': 'application/pdf',
                'raw': content,
                'res_model': statement._name,
                'res_id': statement.id,
            })
        return attachment_id



    def _generate_customer_due_payment_report(self, partner):
        """Generate the customer due payment report."""
        ir_actions_report_sudo = self.env['ir.actions.report'].sudo()
        statement_report_action = self.env.ref('insabhi_due_statement.report_customer_due_print')
        for statement in partner:
            statement_report = statement_report_action.sudo()
            content, _content_type = ir_actions_report_sudo._render_qweb_pdf(statement_report, res_ids=statement.ids)
            attachment_id = self.env['ir.attachment'].create({
                'name':  f"Customer Due Payments - {partner.name}.pdf",
                'type': 'binary',
                'mimetype': 'application/pdf',
                'raw': content,
                'res_model': statement._name,
                'res_id': statement.id,
            })
        return attachment_id

    def _generate_vendor_due_payment_report(self, partner):
        """Generate the vendor due payment report."""

        ir_actions_report_sudo = self.env['ir.actions.report'].sudo()
        statement_report_action = self.env.ref('insabhi_due_statement.report_supplier_due_print')
        for statement in partner:
            statement_report = statement_report_action.sudo()
            content, _content_type = ir_actions_report_sudo._render_qweb_pdf(statement_report, res_ids=statement.ids)
            attachment_id = self.env['ir.attachment'].create({
                'name': f"Vendor Due Payments - {partner.name}.pdf",
                'type': 'binary',
                'mimetype': 'application/pdf',
                'raw': content,
                'res_model': statement._name,
                'res_id': statement.id,
            })
        return attachment_id

    def _generate_vendor_statement_report(self, partner):
        """Generate the vendor statement report."""

        ir_actions_report_sudo = self.env['ir.actions.report'].sudo()
        statement_report_action = self.env.ref('insabhi_due_statement.report_supplier_print')
        for statement in partner:
            statement_report = statement_report_action.sudo()
            content, _content_type = ir_actions_report_sudo._render_qweb_pdf(statement_report, res_ids=statement.ids)
            attachment_id = self.env['ir.attachment'].create({
                'name': f"Vendor Statement - {partner.name}.pdf",
                'type': 'binary',
                'mimetype': 'application/pdf',
                'raw': content,
                'res_model': statement._name,
                'res_id': statement.id,
            })
        return attachment_id


    def _compute_set_statments(self):
        for rec in self:
            if not rec.company_id:
                rec.company_id = self.env.user.company_id

            rec.is_set_statments = False

            if rec.statments == 'due':
                rec.is_set_statments = True
                due_id = self.env['account.move'].search([('partner_id', '=', rec.id), (
                'move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'entry']),
                                                          ('state', 'in', ['posted']),
                                                          ('amount_residual_signed', '!=', 0)])
                for record in due_id:
                    record.is_set_statments = rec.is_set_statments

            elif rec.statments == 'overdue':
                today = date.today()
                rec.is_set_statments = True
                due_id = self.env['account.move'].search(
                    [('partner_id', '=', rec.id),
                     ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'entry']),
                     ('state', 'in', ['posted'])])
                set_list = []
                for record in due_id:
                    if record.invoice_date:
                        start_date = fields.Date.from_string(today)
                        end_date = fields.Date.from_string(record.invoice_date_due)
                        if start_date > end_date:
                            set_list.append(record.id)
                            record.is_set_statments = rec.is_set_statments
                    else:
                        record.is_set_statments = False

            elif rec.statments == 'both':
                rec.is_set_statments = True
                due_id = self.env['account.move'].sudo().search(
                    [('partner_id', '=', rec.id),
                     ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'entry']),
                     ('state', 'in', ['posted'])])
                for record in due_id:
                    record.sudo().is_set_statments = rec.is_set_statments

            else:
                # rec.is_set_statments = True
                due_id = self.env['account.move'].sudo().search(
                    [('partner_id', '=', rec.id),
                     ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'entry']),
                     ('state', 'in', ['posted'])])
                for record in due_id:
                    record.sudo().is_set_statments = False
            rec.sudo()._get_amounts_and_date_amount()

    def do_process_statement_filter(self):
        account_invoice_obj = self.env['account.move']
        statement_line_obj = self.env['bi.statement.line']
        account_payment_obj = self.env['account.payment']
        inv_list = []
        for record in self:
            from_date = record.statement_from_date
            to_date = record.statement_to_date
            filter_selection = record.filter_selection

            if from_date:
                final_initial_bal = 0.0

                in_bal = account_invoice_obj.search([('partner_id', '=', record.id), \
                                                     ('move_type', 'in', ['out_invoice', 'out_refund']),
                                                     ('state', 'in', ['posted']), \
                                                     ('invoice_date', '<', from_date), ])

                for inv in in_bal:
                    final_initial_bal += inv.amount_residual

                entry = account_invoice_obj.search([('partner_id', '=', record.id), \
                                                    ('move_type', 'in', ['entry']), ('state', 'in', ['posted']), \
                                                    ('date', '<', from_date), ])

                for move in entry:
                    final_initial_bal += move.amount_residual

                in_pay_bal = account_payment_obj.search([('partner_id', '=', record.id), \
                                                         ('state', 'in', ['posted', 'reconciled']),
                                                         ('date', '<', from_date), \
                                                         ('partner_type', '=', 'customer')])

                for pay in in_pay_bal:
                    final_initial_bal -= pay.amount

                if final_initial_bal:
                    record.write({'initial_bal': final_initial_bal})

            domain_payment = [('partner_type', '=', 'customer'), ('state', 'in', ['posted', 'reconciled']),
                              ('partner_id', '=', record.id), ('payment_type', '=', 'inbound')]
            domain = [('move_type', 'in', ['out_invoice', 'out_refund']), ('state', 'in', ['posted']),
                      ('partner_id', '=', record.id)]
            domain_entry = [('journal_id.name', '!=', 'Inventory Valuation'), ('move_type', 'in', ['entry']),
                            ('state', 'in', ['posted']), ('partner_id', '=', record.id)]
            if from_date:
                domain.append(('invoice_date', '>=', from_date))
                domain_payment.append(('date', '>=', from_date))
                domain_entry.append(('date', '>=', from_date))
                domain_open_bal = [('move_type', 'in', ['out_invoice', 'out_refund']), ('state', 'in', ['posted']),
                                   ('partner_id', '=', record.id), ('invoice_date', '<', from_date)]

            if to_date:
                domain.append(('invoice_date', '<=', to_date))
                domain_payment.append(('date', '<=', to_date))
                domain_entry.append(('date', '<=', to_date))
                domain_open_date_bal = [('move_type', 'in', ['out_invoice', 'out_refund']), ('state', 'in', ['posted']),
                                        ('partner_id', '=', record.id), ('invoice_date', '<', to_date)]

            if filter_selection == 'due':
                domain_entry.append(('amount_residual', '!=', 0))
                domain.append(('amount_residual', '!=', 0))
                domain_payment.append(('amount_residual', '!=', 0))
                domain_entry.append(('amount_paid', '>', 'amount_total'))
                domain.append(('amount_paid', '>', 'amount_total'))
                domain_payment.append(('amount_paid', '>', 'amount_total'))

            if from_date and to_date:
                opening_bal_move = account_invoice_obj.search(domain_open_bal, order='id desc')
            elif from_date:
                opening_bal_move = account_invoice_obj.search(domain_open_bal, order='id desc')
            elif to_date:
                opening_bal_move = account_invoice_obj.search(domain_open_date_bal, order='id desc')
            else:
                opening_bal_move = account_invoice_obj

            opening_balance = 0.0

            if opening_bal_move:
                record.update({'opening_balance': sum(opening_bal_move.mapped('result'))})
            else:
                record.update({'opening_balance': 0.0})

            lines_to_be_delete = statement_line_obj.search([('partner_id', '=', record.id)])
            lines_to_be_delete.unlink()

            move_entry = account_invoice_obj.search(domain_entry)
            invoices = account_invoice_obj.search(domain)
            payments = account_payment_obj.search(domain_payment)
            if invoices:
                for invoice in invoices.sorted(key=lambda r: r.invoice_date):
                    vals = {
                        'partner_id': invoice.partner_id.id or False,
                        'state': invoice.state or False,
                        'invoice_date': invoice.invoice_date,
                        'invoice_date_due': invoice.invoice_date_due,
                        'result': invoice.result or 0.0,
                        'name': invoice.name or '',
                        'amount_total': invoice.amount_total or 0.0,
                        'credit_amount': invoice.credit_amount or 0.0,
                        'invoice_id': invoice.id,
                    }
                    test = statement_line_obj.create(vals)
            # if move_entry:
            #     for invoice in move_entry.sorted(key=lambda r: r.invoice_date):
            #         vals = {
            #             'partner_id': invoice.partner_id.id or False,
            #             'state': invoice.state or False,
            #             'invoice_date': invoice.invoice_date,
            #             'result': invoice.result or 0.0,
            #             'name': invoice.name or '',
            #             'amount_total': invoice.amount_total or 0.0,
            #             'credit_amount': invoice.credit_amount or 0.0,
            #             'invoice_id': invoice.id,
            #         }
            #         test = statement_line_obj.create(vals)

            if payments:
                for payment in payments.sorted(key=lambda r: r.invoice_date):
                    vals = {
                        'partner_id': payment.partner_id.id or False,
                        'state': payment.state or False,
                        'invoice_date': payment.date,  # Payment date
                        'result': payment.amount or 0.0,  # Payments reduce the balance
                        'name': payment.name or '',  # Payment reference
                        'amount_total': payment.amount or 0.0,  # Total payment amount
                        'credit_amount': payment.amount or 0.0,  # Payment is treated as a credit
                        'invoice_id': False,  # No invoice link for payments
                        # 'payment_id': payment.id,  # Add this field if `bi.statement.line` has a link to payments
                    }
                    statement_line_obj.create(vals)

    @api.onchange('filter_selection')
    def _onchange_statement_dates(self):
        for rec in self:
            if rec.filter_selection:
                rec.statement_to_date = False
                rec.statement_from_date = False
                rec.vendor_statement_to_date = False
                rec.vendor_statement_from_date = False

    @api.depends('category_id')
    def _compute_hide_statement(self):
        for rec in self:
            category_names = rec.category_id.mapped('name')
            if 'Customer' in category_names and 'Supplier' in category_names:
                rec.hide_statement = False
            elif 'Customer' in category_names:
                rec.hide_statement = 'hide_vendor_statement'
            elif 'Supplier' in category_names:
                rec.hide_statement = 'hide_customer_statement'
            else:
                rec.hide_statement = 'hide_both'

    def do_process_vendor_statement_filter(self):
        account_invoice_obj = self.env['account.move']
        vendor_statement_line_obj = self.env['bi.vendor.statement.line']
        account_payment_obj = self.env['account.payment']
        for record in self:
            from_date = record.vendor_statement_from_date
            to_date = record.vendor_statement_to_date
            filter_selection = record.filter_selection

            if from_date:

                final_initial_bal = 0.0

                in_bal = account_invoice_obj.search([('partner_id', '=', record.id), \
                                                     ('move_type', 'in', ['in_invoice', 'in_refund']),
                                                     ('state', 'in', ['posted']), ('invoice_date', '<', from_date)])
                for inv in in_bal:
                    final_initial_bal += inv.amount_residual
                entry = account_invoice_obj.search([('partner_id', '=', record.id), \
                                                    ('move_type', 'in', ['entry']), ('state', 'in', ['posted']), \
                                                    ('date', '<', from_date), ])

                for move in entry:
                    final_initial_bal += move.amount_residual

                in_pay_bal = account_payment_obj.search([('partner_id', '=', record.id), \
                                                         ('state', 'in', ['posted', 'reconciled']),
                                                         ('date', '<', from_date), \
                                                         ('partner_type', '=', 'supplier')])

                for pay in in_pay_bal:
                    final_initial_bal -= pay.amount

                if final_initial_bal:
                    record.write({'initial_supp_bal': -final_initial_bal})

            domain_payment = [('partner_type', '=', 'supplier'), ('state', 'in', ['posted', 'reconciled']),
                              ('partner_id', '=', record.id), ('payment_type', '=', 'outbound')]
            domain = [('move_type', 'in', ['in_invoice', 'in_refund']), ('state', 'in', ['posted']),
                      ('partner_id', '=', record.id)]
            domain_entry = [('journal_id.name', '!=', 'Inventory Valuation'), ('move_type', 'in', ['entry']),
                            ('state', 'in', ['posted']), ('partner_id', '=', record.id)]

            if from_date:
                domain.append(('invoice_date', '>=', from_date))
                domain_payment.append(('date', '>=', from_date))
                domain_entry.append(('date', '>=', from_date))
                domain_open_bal = [('move_type', 'in', ['in_invoice', 'in_refund']), ('state', 'in', ['posted']),
                                   ('partner_id', '=', record.id), ('invoice_date', '<', from_date)]

            if to_date:
                domain.append(('invoice_date', '<=', to_date))
                domain_payment.append(('date', '<=', to_date))
                domain_entry.append(('date', '<=', to_date))
                domain_open_date_bal = [('move_type', 'in', ['in_invoice', 'in_refund']), ('state', 'in', ['posted']),
                                        ('partner_id', '=', record.id), ('invoice_date', '<', to_date)]

            if filter_selection == 'due':
                domain_entry.append(('amount_residual', '!=', 0))
                domain.append(('amount_residual', '!=', 0))
                domain_payment.append(('amount_residual', '!=', 0))
                domain_entry.append(('amount_paid', '>', 'amount_total'))
                domain.append(('amount_paid', '>', 'amount_total'))
                domain_payment.append(('amount_paid', '>', 'amount_total'))

            if from_date and to_date:
                opening_bal_vendor = account_invoice_obj.search(domain_open_bal, order='id desc')
            elif from_date:
                opening_bal_vendor = account_invoice_obj.search(domain_open_bal, order='id desc')
            elif to_date:
                opening_bal_vendor = account_invoice_obj.search(domain_open_date_bal, order='id desc')
            else:
                opening_bal_vendor = account_invoice_obj

            opening_balance = 0.0

            if opening_bal_vendor:
                record.update({'vendor_opening_balance': sum(opening_bal_vendor.mapped('result'))})
            else:
                record.update({'vendor_opening_balance': 0.0})

            lines_to_be_delete = vendor_statement_line_obj.search([('partner_id', '=', record.id)])
            lines_to_be_delete.unlink()

            move_entry = account_invoice_obj.search(domain_entry)
            invoices = account_invoice_obj.search(domain)
            payments = account_payment_obj.search(domain_payment)
            if invoices:
                for invoice in invoices.sorted(key=lambda r: r.invoice_date):
                    vals = {
                        'partner_id': invoice.partner_id.id or False,
                        'state': invoice.state or False,
                        'invoice_date': invoice.invoice_date,
                        'invoice_date_due': invoice.invoice_date_due,
                        'result': invoice.result or 0.0,
                        'name': invoice.name or '',
                        'amount_total': invoice.amount_total or 0.0,
                        'credit_amount': invoice.credit_amount or 0.0,
                        'invoice_id': invoice.id,
                    }
                    vendor_statement_line_obj.create(vals)

            # if move_entry:
            #     for invoice in move_entry.sorted(key=lambda r: r.name):
            #         vals = {
            #             'partner_id': invoice.partner_id.id or False,
            #             'state': invoice.state or False,
            #             'invoice_date': invoice.invoice_date,
            #             'result': invoice.result or 0.0,
            #             'name': invoice.name or '',
            #             'amount_total': invoice.amount_total or 0.0,
            #             'credit_amount': invoice.credit_amount or 0.0,
            #             'invoice_id': invoice.id,
            #         }
            #         vendor_statement_line_obj.create(vals)

            if payments:
                for payment in payments.sorted(key=lambda r: r.invoice_date):
                    vals = {
                        'partner_id': payment.partner_id.id or False,
                        'state': payment.state or False,
                        'invoice_date': payment.date,  # Payment date
                        'result': payment.amount or 0.0,  # Payments reduce the balance
                        'name': payment.name or '',  # Payment reference
                        'amount_total': payment.amount or 0.0,  # Total payment amount
                        'credit_amount': payment.amount or 0.0,  # Payment is treated as a credit
                        'invoice_id': False,  # No invoice link for payments
                        # 'payment_id': payment.id,  # Add this field if `bi.statement.line` has a link to payments
                    }
                    vendor_statement_line_obj.create(vals)

    def do_send_statement_filter(self):
        unknown_mails = 0
        for partner in self:
            partners_to_email = [child for child in partner.child_ids if child.type == 'invoice' and child.email]
            if not partners_to_email and partner.email:
                partners_to_email = [partner]
            if partners_to_email:
                for partner_to_email in partners_to_email:
                    mail_template_id = self.env.ref('insabhi_due_statement.email_template_customer_statement_filter')
                    mail_template_id.send_mail(partner_to_email.id)
                    msg = _('Customer Filter Statement email sent to %s-%s' % (partner.name, partner.email))

                    partner.message_post(body=msg)
                if partner not in partner_to_email:
                    self.message_post([partner.id], body=_('Customer Filter Statement email sent to %s' % ', '.join(
                        ['%s <%s>' % (partner.name, partner.email) for partner in partners_to_email])))
        return unknown_mails

    def _cron_send_overdue_statement(self):
        partners = self.env['res.partner'].search([('opt_statement', '=', False)])
        company = self.env.user.company_id
        if company.send_overdue_statement:
            partners.do_partner_mail()
        return True

    def _cron_supplier_send_overdue_statement(self):
        partners = self.env['res.partner'].search([('opt_statement', '=', False)])
        company = self.env.user.company_id
        if company.supplier_overdue_statement:
            partners.supplier_do_partner_mail()
        return True

    def _cron_send_customer_monthly_statement(self):
        partners = self.env['res.partner'].search([])
        company = self.env.user.company_id
        if company.auto_monthly_statement and company.send_statement:
            partners.customer_monthly_send_mail()

        return True

    def _cron_send_supplier_monthly_statement(self):
        partners = self.env['res.partner'].search([])
        company = self.env.user.company_id
        if company.sup_auto_weekly_statement and company.supplier_statement:
            partners.supplier_monthly_send_mail()

        return True

    def _cron_send_customer_weekly_statement(self):
        partners = self.env['res.partner'].search([])
        company = self.env.user.company_id
        today = date.today()
        if company.auto_weekly_statement and company.weekly_days and company.send_statement:
            if int(company.weekly_days) == int(today.weekday()):
                partners.customer_weekly_send_mail()

        return True

    def _cron_send_supplier_weekly_statement(self):
        partners = self.env['res.partner'].search([])
        company = self.env.user.company_id
        today = date.today()

        if company.sup_auto_weekly_statement and company.sup_weekly_days and company.supplier_statement:
            if int(company.sup_weekly_days) == int(today.weekday()):
                partners.supplier_weekly_send_mail()

        return True

    def do_due_partner_mail(self):
        unknown_mails = 0
        for partner in self:
            partner.payment_amount_due_amt = None
            partner._get_amounts_and_date_amount()
            if partner.payment_amount_due_amt == 0.00:
                pass
            else:

                if partner.email:

                    template = self.env.ref('insabhi_due_statement.bi_email_template_customer_due_statement')
                    report = self.env.ref('insabhi_due_statement.report_customer_due_print')

                    attachments = []

                    if report.report_type in ['qweb-html', 'qweb-pdf']:
                        result, report_format = self.env['ir.actions.report']._render_qweb_pdf(report, [partner.id])
                    else:
                        res = self.env['ir.actions.report']._render(report, [partner.id])
                        if not res:
                            raise UserError(_('Unsupported report type %s found.', report.report_type))
                        result, report_format = res

                    # TODO in trunk, change return format to binary to match message_post expected format

                    template.sudo().with_context(monthly_attachments=attachments).send_mail(partner.id)
                    msg = _('Customer due Statement email sent to %s-%s' % (partner.name, partner.email))

                    partner.message_post(body=msg)
                else:
                    unknown_mails += 1

        return unknown_mails

    def do_due_supplier_partner_mail(self):
        unknown_mails = 0
        for partner in self:

            partner.sudo().payment_amount_due_amt = None
            partner.sudo()._get_amounts_and_date_amount()
            if partner.sudo().payment_amount_due_amt_supplier == 0.00:
                pass
            else:
                if partner.email:
                    template = self.env.ref(
                        'insabhi_due_statement.email_template_supplier_due_statement')
                    report = self.env.ref('insabhi_due_statement.report_supplier_due_print')

                    attachments = []

                    if report.report_type in ['qweb-html', 'qweb-pdf']:
                        result, report_format = self.env['ir.actions.report']._render_qweb_pdf(report, [partner.id])
                    else:
                        res = self.env['ir.actions.report']._render(report, [partner.id])
                        if not res:
                            raise UserError(_('Unsupported report type %s found.', report.report_type))
                        result, report_format = res

                    # TODO in trunk, change return format to binary to match message_post expected format
                    result = base64.b64encode(result)

                    msg = _('Supplier Due Statement email sent to %s-%s' % (partner.name, partner.email))

                    partner.sudo().message_post(body=msg)
                else:
                    unknown_mails += 1

        return unknown_mails

    def do_partner_mail(self):
        unknown_mails = 0
        for partner in self:
            partner.sudo().payment_amount_overdue_amt = None
            partner.sudo()._get_amounts_and_date_amount()
            if partner.sudo().payment_amount_overdue_amt == 0.00:
                pass
            else:

                if partner.email:
                    template = self.env.user.company_id.overdue_statement_template_id
                    if not template:
                        template = self.env.ref('insabhi_due_statement.email_template_customer_over_due_statement')

                    report = self.env.ref('insabhi_due_statement.report_customer_overdue_print')

                    attachments = []

                    if report.report_type in ['qweb-html', 'qweb-pdf']:
                        result, report_format = self.env['ir.actions.report']._render_qweb_pdf(report, [partner.id])
                    else:
                        res = self.env['ir.actions.report']._render(report, [partner.id])
                        if not res:
                            raise UserError(_('Unsupported report type %s found.', report.report_type))
                        result, report_format = res

                    # TODO in trunk, change return format to binary to match message_post expected format

                    template.sudo().with_context(monthly_attachments=attachments).sudo().send_mail(partner.id)

                    msg = _('Customer Overdue Statement email sent to %s-%s' % (partner.name, partner.email))

                    partner.sudo().message_post(body=msg)
                else:
                    unknown_mails += 1

        return unknown_mails

    def supplier_do_partner_mail(self):
        unknown_mails = 0
        for partner in self:
            partner.sudo().payment_amount_overdue_amt = None
            partner.sudo()._get_amounts_and_date_amount()
            if partner.sudo().payment_amount_overdue_amt_supplier == 0.00:
                pass
            else:
                if partner.email:
                    template = self.env.user.company_id.sup_overdue_statement_temp_id
                    if not template:
                        template = self.env.ref(
                            'insabhi_due_statement.email_template_supplier_over_due_statement')

                    report = self.env.ref('insabhi_due_statement.report_supplier_overdue_print')

                    attachments = []

                    if report.report_type in ['qweb-html', 'qweb-pdf']:
                        result, report_format = self.env['ir.actions.report']._render_qweb_pdf(report, [partner.id])
                    else:
                        res = self.env['ir.actions.report']._render(report, [partner.id])
                        if not res:
                            raise UserError(_('Unsupported report type %s found.', report.report_type))
                        result, report_format = res

                    # TODO in trunk, change return format to binary to match message_post expected format
                    result = base64.b64encode(result)

                    template.sudo().with_context(monthly_attachments=attachments).sudo().send_mail(partner.id)

                    msg = _('Supplier Overdue Statement email sent to %s-%s' % (partner.name, partner.email))

                    partner.sudo().message_post(body=msg)
                else:
                    unknown_mails += 1

        return unknown_mails

    def do_process_monthly_statement_filter(self):
        account_invoice_obj = self.env['account.move']
        statement_line_obj = self.env['monthly.statement.line']
        partner_obj = self.env['res.partner'].search([])
        for record in partner_obj:

            today = date.today()
            d = today - relativedelta(months=1)

            start_date = date(d.year, d.month, 1)
            end_date = date(today.year, today.month, 1) - relativedelta(days=1)

            from_date = str(start_date)
            to_date = str(end_date)

            domain = [('move_type', 'in', ['out_invoice', 'out_refund']), ('state', 'in', ['posted']),
                      ('partner_id', '=', record.id)]
            if from_date:
                domain.append(('invoice_date', '>=', from_date))
            if to_date:
                domain.append(('invoice_date', '<=', to_date))

            invoices = account_invoice_obj.search(domain)
            for invoice in invoices.sorted(key=lambda r: r.name):
                vals = {
                    'partner_id': invoice.partner_id.id or False,
                    'state': invoice.state or False,
                    'invoice_date': invoice.invoice_date,
                    'invoice_date_due': invoice.invoice_date_due,
                    'result': invoice.result or 0.0,
                    'name': invoice.name or '',
                    'amount_total': invoice.amount_total or 0.0,
                    'credit_amount': invoice.credit_amount or 0.0,
                    'invoice_id': invoice.id,
                    'invoice_type': 'invoice',
                }
                exist_line = statement_line_obj.search([('invoice_id', '=', invoice.id)])
                exist_line.write(vals)
                if not exist_line:
                    ob = statement_line_obj.create(vals)

    def do_process_supplier_monthly_statement_filter(self):
        account_invoice_obj = self.env['account.move']
        statement_line_obj = self.env['monthly.statement.line']
        partner_obj = self.env['res.partner'].search([])
        for record in partner_obj:
            today = date.today()
            d = today - relativedelta(months=1)

            start_date = date(d.year, d.month, 1)
            end_date = date(today.year, today.month, 1) - relativedelta(days=1)

            from_date = str(start_date)
            to_date = str(end_date)
            domain = [('move_type', 'in', ['in_invoice', 'in_refund']), ('state', 'in', ['posted']),
                      ('partner_id', '=', record.id)]

            if from_date:
                domain.append(('invoice_date', '>=', from_date))
            if to_date:
                domain.append(('invoice_date', '<=', to_date))

            invoices = account_invoice_obj.search(domain)
            for invoice in invoices.sorted(key=lambda r: r.name):
                vals = {
                    'partner_id': invoice.partner_id.id or False,
                    'state': invoice.state or False,
                    'bill_date': invoice.invoice_date,
                    'invoice_date_due': invoice.invoice_date_due,
                    'result': invoice.result or 0.0,
                    'name': invoice.name or '',
                    'amount_total': invoice.amount_total or 0.0,
                    'credit_amount': invoice.credit_amount or 0.0,
                    'invoice_id': invoice.id,
                    'invoice_type': 'bill',
                }
                exist_line = statement_line_obj.search([('invoice_id', '=', invoice.id)])
                exist_line.write(vals)
                if not exist_line:
                    ob = statement_line_obj.create(vals)

    def do_process_weekly_statement_filter(self):
        account_invoice_obj = self.env['account.move']
        statement_line_obj = self.env['weekly.statement.line']
        partner_obj = self.env['res.partner'].search([])
        for record in partner_obj:

            today = date.today()

            start_date = today + timedelta(-today.weekday(), weeks=-1)
            end_date = today + timedelta(-today.weekday() - 1)

            from_date = str(start_date)
            to_date = str(end_date)

            domain = [('move_type', 'in', ['out_invoice', 'out_refund']), ('state', 'in', ['posted']),
                      ('partner_id', '=', record.id)]
            if from_date:
                domain.append(('invoice_date', '>=', from_date))
            if to_date:
                domain.append(('invoice_date', '<=', to_date))

            invoices = account_invoice_obj.search(domain)

            for invoice in invoices.sorted(key=lambda r: r.name):
                vals = {
                    'partner_id': invoice.partner_id.id or False,
                    'state': invoice.state or False,
                    'invoice_date': invoice.invoice_date,
                    'invoice_date_due': invoice.invoice_date_due,
                    'result': invoice.result or 0.0,
                    'name': invoice.name or '',
                    'amount_total': invoice.amount_total or 0.0,
                    'credit_amount': invoice.credit_amount or 0.0,
                    'invoice_id': invoice.id,
                    'invoice_type': 'invoice',
                }
                exist_line = statement_line_obj.search([('invoice_id', '=', invoice.id)])
                exist_line.write(vals)
                if not exist_line:
                    ob = statement_line_obj.create(vals)

    def do_process_supplier_weekly_statement_filter(self):
        account_invoice_obj = self.env['account.move']
        statement_line_obj = self.env['weekly.statement.line']
        partner_obj = self.env['res.partner'].search([])
        for record in partner_obj:

            today = date.today()

            start_date = today + timedelta(-today.weekday(), weeks=-1)
            end_date = today + timedelta(-today.weekday() - 1)

            from_date = str(start_date)
            to_date = str(end_date)

            domain = [('move_type', 'in', ['in_invoice', 'in_refund']), ('state', 'in', ['posted']),
                      ('partner_id', '=', record.id)]
            if from_date:
                domain.append(('invoice_date', '>=', from_date))
            if to_date:
                domain.append(('invoice_date', '<=', to_date))

            invoices = account_invoice_obj.search(domain)

            for invoice in invoices.sorted(key=lambda r: r.name):
                vals = {
                    'partner_id': invoice.partner_id.id or False,
                    'state': invoice.state or False,
                    'bill_date': invoice.invoice_date,
                    'invoice_date_due': invoice.invoice_date_due,
                    'result': invoice.result or 0.0,
                    'name': invoice.name or '',
                    'amount_total': invoice.amount_total or 0.0,
                    'credit_amount': invoice.credit_amount or 0.0,
                    'invoice_id': invoice.id,
                    'invoice_type': 'bill',
                }
                exist_line = statement_line_obj.search([('invoice_id', '=', invoice.id)])

                exist_line.write(vals)
                if not exist_line:
                    ob = statement_line_obj.create(vals)

    def customer_monthly_send_mail(self):
        unknown_mails = 0
        for partner in self:
            partner.sudo().monthly_payment_amount_due_amt = None
            partner.sudo()._get_amounts_and_date_amount()
            if partner.sudo().opt_statement == False:
                if partner.sudo().monthly_payment_amount_due_amt == 0.00:
                    pass
                else:
                    if partner.email:
                        template = self.env.user.company_id.monthly_template_id

                        report = self.env.ref('insabhi_due_statement.report_customer_monthly_print')

                        attachments = []

                        if report.report_type in ['qweb-html', 'qweb-pdf']:
                            result, report_format = self.env['ir.actions.report']._render_qweb_pdf(report, [partner.id])
                        else:
                            res = self.env['ir.actions.report']._render(report, [partner.id])
                            if not res:
                                raise UserError(_('Unsupported report type %s found.', report.report_type))
                            result, report_format = res

                        # TODO in trunk, change return format to binary to match message_post expected format
                        result = base64.b64encode(result)

                        template.sudo().with_context(monthly_attachments=attachments).sudo().send_mail(partner.id)

                        msg = _('Customer Monthly Statement email sent to %s-%s' % (partner.name, partner.email))

                        partner.sudo().message_post(body=msg)
                    else:
                        unknown_mails += 1
        return unknown_mails

    def supplier_monthly_send_mail(self):
        unknown_mails = 0
        for partner in self:
            partner.sudo().sup_monthly_payment_amount_due_amt = None
            partner.sudo()._get_amounts_and_date_amount()
            if partner.sudo().opt_statement == False:
                if partner.sudo().sup_monthly_payment_amount_due_amt == 0.00:
                    pass
                else:
                    if partner.email:
                        template = self.env.user.company_id.sup_monthly_template_id

                        report = self.env.ref('insabhi_due_statement.report_supplier_monthly_print')

                        attachments = []

                        if report.report_type in ['qweb-html', 'qweb-pdf']:
                            result, report_format = self.env['ir.actions.report']._render_qweb_pdf(report, [partner.id])
                        else:
                            res = self.env['ir.actions.report']._render(report, [partner.id])
                            if not res:
                                raise UserError(_('Unsupported report type %s found.', report.report_type))
                            result, report_format = res

                        # TODO in trunk, change return format to binary to match message_post expected format
                        result = base64.b64encode(result)

                        template.sudo().with_context(monthly_attachments=attachments).sudo().send_mail(partner.id)

                        msg = _('Supplier Monthly Statement email sent to %s-%s' % (partner.name, partner.email))

                        partner.sudo().message_post(body=msg)
                    else:
                        unknown_mails += 1
        return unknown_mails

    def customer_weekly_send_mail(self):
        unknown_mails = 0
        for partner in self:

            partner.sudo().weekly_payment_amount_due_amt = None
            partner.sudo()._get_amounts_and_date_amount()
            if partner.sudo().opt_statement == False:
                if partner.sudo().weekly_payment_amount_due_amt == 0.00:
                    pass
                else:
                    if partner.email:

                        template = self.env.user.company_id.weekly_template_id

                        report = self.env.ref('insabhi_due_statement.report_customer_weekly_print')

                        attachments = []

                        if report.report_type in ['qweb-html', 'qweb-pdf']:
                            result, report_format = self.env['ir.actions.report']._render_qweb_pdf(report, [partner.id])
                        else:
                            res = self.env['ir.actions.report']._render(report, [partner.id])
                            if not res:
                                raise UserError(_('Unsupported report type %s found.', report.report_type))
                            result, report_format = res

                        # TODO in trunk, change return format to binary to match message_post expected format
                        result = base64.b64encode(result)

                        template.with_context(monthly_attachments=attachments).sudo().sudo().send_mail(partner.id)

                        msg = _('Customer Weekly Statement email sent to %s-%s' % (partner.name, partner.email))

                        partner.sudo().sudo().message_post(body=msg)
                    else:
                        unknown_mails += 1
        return unknown_mails

    def supplier_weekly_send_mail(self):
        unknown_mails = 0
        for partner in self:
            partner.sudo().sup_weekly_payment_amount_due_amt = None
            partner.sudo()._get_amounts_and_date_amount()
            if partner.sudo().opt_statement == False:
                if partner.sudo().sup_weekly_payment_amount_due_amt == 0.00:
                    pass
                else:
                    if partner.email:
                        template = self.env.user.company_id.sup_weekly_template_id

                        report = self.env.ref('insabhi_due_statement.report_supplier_weekly_print')

                        attachments = []

                        if report.report_type in ['qweb-html', 'qweb-pdf']:
                            result, report_format = self.env['ir.actions.report']._render_qweb_pdf(report, [partner.id])
                        else:
                            res = self.env['ir.actions.report']._render(report, [partner.id])
                            if not res:
                                raise UserError(_('Unsupported report type %s found.', report.report_type))
                            result, report_format = res

                        # TODO in trunk, change return format to binary to match message_post expected format
                        result = base64.b64encode(result)

                        template.with_context(monthly_attachments=attachments).sudo().send_mail(partner.id)

                        msg = _('Supplier Weekly Statement email sent to %s-%s' % (partner.name, partner.email))

                        partner.sudo().message_post(body=msg)
                    else:
                        unknown_mails += 1
        return unknown_mails

    def customer_send_mail(self):
        unknown_mails = 0
        for partner in self:
            partners_to_email = [child for child in partner.child_ids if child.type == 'invoice' and child.email]
            if not partners_to_email and partner.email:
                partners_to_email = [partner]
            if partners_to_email:
                for partner_to_email in partners_to_email:
                    mail_template_id = self.env.ref('insabhi_due_statement.email_template_customer_statement')
                    mail_template_id.send_mail(partner_to_email.id)
                    msg = _('Customer Statement email sent to %s-%s' % (partner.name, partner.email))

                    partner.message_post(body=msg)
                if partner not in partner_to_email:
                    self.message_post([partner.id], body=_('Customer Statement email sent to %s' % ', '.join(
                        ['%s <%s>' % (partner.name, partner.email) for partner in partners_to_email])))
        return unknown_mails

    def supplier_send_mail(self):
        unknown_mails = 0
        for partner in self:
            partners_to_email = [child for child in partner.child_ids if child.type == 'invoice' and child.email]
            if not partners_to_email and partner.email:
                partners_to_email = [partner]

            if partners_to_email:
                for pe in partners_to_email:
                    mail_template_id = self.env.ref('insabhi_due_statement.email_template_supplier_statement')
                    mail_template_id.send_mail(pe.id)
                    msg = _('Supplier Statement email sent to %s-%s' % (partner.name, partner.email))

                    partner.message_post(body=msg)
                if partner not in partners_to_email:
                    self.message_post([partner.id], body=_('Supplier Statement email sent to %s' % ', '.join(
                        ['%s <%s>' % (partner.name, partner.email) for partner in partners_to_email])))

        return unknown_mails

    def do_button_due_print(self):
        return self.env.ref('insabhi_due_statement.report_customer_due_print').report_action(self)

    def do_button_supplier_due_print(self):
        return self.env.ref('insabhi_due_statement.report_supplier_due_print').report_action(self)

    def do_button_print(self):
        return self.env.ref('insabhi_due_statement.report_customer_overdue_print').report_action(self)

    def do_supplier_button_print(self):
        return self.env.ref('insabhi_due_statement.report_supplier_overdue_print').report_action(self)

    def do_button_print_statement(self):
        return self.env.ref('insabhi_due_statement.report_customert_print').report_action(self)

    def do_supplier_button_print_statement(self):
        return self.env.ref('insabhi_due_statement.report_customert_print').report_action(self)

    def do_button_print_vendor_statement(self):
        return self.env.ref('insabhi_due_statement.report_supplier_print').report_action(self)

    def do_print_statement_filter(self):
        return self.env.ref('insabhi_due_statement.report_customer_statement_filter_print').report_action(self)

    def do_print_vendor_statement_filter(self):
        return self.env.ref('insabhi_due_statement.report_supplier_filter_print').report_action(self)

    def do_customer_statement_mail(self):
        account_invoice_obj = self.env['account.move']
        statement_line_obj = self.env['custom.statement.line']
        amount_due = amount_overdue = 0.0

        for partner in self:
            if partner.email:

                mail_template_id = self.env.ref('insabhi_due_statement.email_template_customer_statement_custom_')

                if self._context.get('overdue_duration'):
                    to_date = fields.date.today()
                    from_date = to_date - relativedelta(days=30)
                    if self._context.get('overdue_duration') == 'custom':
                        from_date = self._context.get('from_date')
                        to_date = self._context.get('to_date')
                    else:
                        _duration = self._context.get('overdue_duration')
                        to_date = fields.date.today()
                        if _duration == '3m':
                            from_date = to_date - relativedelta(months=3)
                        else:
                            from_date = to_date - relativedelta(days=int(_duration))

                    domain = [('move_type', 'in', ['out_invoice', 'out_refund']), ('state', '=', 'posted'),
                              ('partner_id', '=', partner.id)]
                    if from_date:
                        domain.append(('invoice_date', '>=', from_date))
                    if to_date:
                        domain.append(('invoice_date', '<=', to_date))

                    partner.sudo().write({
                        'custom_from_date': from_date,
                        'custom_to_date': to_date
                    })

                    lines_to_be_delete = statement_line_obj.search([('partner_id', '=', partner.id)])
                    lines_to_be_delete.unlink()

                    invoices = account_invoice_obj.search(domain)
                    for invoice in invoices.sorted(key=lambda r: r.name):
                        vals = {
                            'partner_id': invoice.partner_id.id or False,
                            'state': invoice.state or False,
                            'date_invoice': invoice.invoice_date,
                            'date_due': invoice.invoice_date_due,
                            'number': invoice.name or '',
                            'result': invoice.result or 0.0,
                            'name': invoice.name or '',
                            'amount_total': invoice.amount_total or 0.0,
                            'credit_amount': invoice.credit_amount or 0.0,
                            'invoice_id': invoice.id,
                        }
                        statement_line_obj.create(vals)
                    if invoices:
                        mail_template_id.send_mail(partner.id)
                        msg = _('Statement sent to %s - %s' % (partner.name, partner.email))
                        partner.message_post(body=msg)
