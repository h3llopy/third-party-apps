# flake8: noqa
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, fields, _
from odoo.tools.misc import format_date
# from odoo.exceptions import ValidationError


class ReportPartnerLedger(models.AbstractModel):
    _inherit = "account.partner.ledger"

    # @api.model
    # def get_lines(self, options, line_id=None):
    #     """
    #     Add document number on partner ledger
    #     """
    #     lines = super(ReportPartnerLedger, self).get_lines(
    #         options, line_id=line_id)
    #     for line in lines:
    #         # only lines with unfoldable are the partner line
    #         if line.get('unfoldable'):
    #             partner_id = int(line['id'].split('partner_')[1])
    #             partner = self.env['res.partner'].browse(partner_id)
    #             if partner.main_id_number and partner.main_id_category_id:
    #                 line['name'] += " (%s: %s)" % (
    #                     partner.main_id_category_id.code,
    #                     partner.main_id_number)
    #     return lines

    @api.model
    def get_lines(self, options, line_id=None):
        lines = []
        if line_id:
            line_id = line_id.replace('partner_', '')
        context = self.env.context
        company_id = context.get('company_id') or self.env.user.company_id

        #If a default partner is set, we only want to load the line referring to it.
        if options.get('partner_id'):
            line_id = options['partner_id']

        grouped_partners = self.group_by_partner_id(options, line_id)
        sorted_partners = sorted(grouped_partners, key=lambda p: p.name or '')
        unfold_all = context.get('print_mode') and not options.get('unfolded_lines') or options.get('partner_id')
        total_initial_balance = total_debit = total_credit = total_balance = 0.0
        for partner in sorted_partners:
            debit = grouped_partners[partner]['debit']
            credit = grouped_partners[partner]['credit']
            balance = grouped_partners[partner]['balance']
            initial_balance = grouped_partners[partner]['initial_bal']['balance']
            total_initial_balance += initial_balance
            total_debit += debit
            total_credit += credit
            total_balance += balance
            partner_name = partner.name
            if partner.main_id_number and partner.main_id_category_id:
                partner_name += " (%s: %s)" % (
                    partner.main_id_category_id.code, partner.main_id_number)
            lines.append({
                'id': 'partner_' + str(partner.id),
                # 'name': partner.name,
                'name': partner_name,
                'columns': [{'name': v} for v in [self.format_value(initial_balance), self.format_value(debit), self.format_value(credit), self.format_value(balance)]],
                'level': 2,
                'trust': partner.trust,
                'unfoldable': True,
                'unfolded': 'partner_' + str(partner.id) in options.get('unfolded_lines') or unfold_all,
                'colspan': 5,
            })
            used_currency = self.env.user.company_id.currency_id
            if 'partner_' + str(partner.id) in options.get('unfolded_lines') or unfold_all:
                progress = initial_balance
                domain_lines = []
                amls = grouped_partners[partner]['lines']
                too_many = False
                if len(amls) > 80 and not context.get('print_mode'):
                    amls = amls[-80:]
                    too_many = True
                for line in amls:
                    if options.get('cash_basis'):
                        line_debit = line.debit_cash_basis
                        line_credit = line.credit_cash_basis
                    else:
                        line_debit = line.debit
                        line_credit = line.credit
                    line_currency = line.company_id.currency_id.with_context(date=amls.env.context.get('date') or fields.Date.today())
                    line_debit = line_currency.compute(line_debit, used_currency)
                    line_credit = line_currency.compute(line_credit, used_currency)
                    progress_before = progress
                    progress = progress + line_debit - line_credit
                    name = '-'.join(
                        # INICIO CAMBIO
                        (line.move_id.display_name not in ['', '/'] and [line.move_id.display_name] or []) +
                        # (line.move_id.name not in ['', '/'] and [line.move_id.name] or []) +
                        # FIN CAMBIO
                        (line.ref not in ['', '/', False] and [line.ref] or []) +
                        ([line.name] if line.name and line.name not in ['', '/'] else [])
                    )
                    if len(name) > 35 and not self.env.context.get('no_format'):
                        name = name[:32] + "..."
                    caret_type = 'account.move'
                    if line.invoice_id:
                        caret_type = 'account.invoice.in' if line.invoice_id.type in ('in_refund', 'in_invoice') else 'account.invoice.out'
                    elif line.payment_id:
                        caret_type = 'account.payment'
                    domain_lines.append({
                        'id': line.id,
                        'parent_id': 'partner_' + str(partner.id),
                        'name': format_date(self.env, line.date),
                        'columns': [{'name': v} for v in [line.journal_id.code, line.account_id.code, name, line.full_reconcile_id.name, self.format_value(progress_before),
                                    line_debit != 0 and self.format_value(line_debit) or '',
                                    line_credit != 0 and self.format_value(line_credit) or '',
                                    self.format_value(progress)]],
                        'caret_options': caret_type,
                        'level': 4,
                    })
                if too_many:
                    domain_lines.append({
                        'id': 'too_many_' + str(partner.id),
                        'parent_id': 'partner_' + str(partner.id),
                        'action': 'view_too_many',
                        'action_id': 'partner,%s' % (partner.id,),
                        'name': _('There are more than 80 items in this list, click here to see all of them'),
                        'colspan': 8,
                        'columns': [{}],
                    })
                lines += domain_lines
        if not line_id:
            lines.append({
                'id': 'grouped_partners_total',
                'name': _('Total'),
                'level': 0,
                'class': 'o_account_reports_domain_total',
                'columns': [{'name': v} for v in ['', '', '', '', self.format_value(total_initial_balance), self.format_value(total_debit), self.format_value(total_credit), self.format_value(total_balance)]],
            })
        return lines
