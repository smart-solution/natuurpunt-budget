# -*- coding: utf-8 -*-
##############################################################################
#
#    Smart Solution bvba
#    Copyright (C) 2010-Today Smart Solution BVBA (<http://www.smartsolution.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
############################################################################## 

from osv import osv, fields
from openerp.tools.translate import _
import csv 
import base64
from datetime import datetime

class account_budget_detailline(osv.osv):

    _name = 'account.budget.detailline'
    _description = 'account_budget_detailline'

    _columns = { 
        'name': fields.char('Description', size=128, required=True, states={'confirm':[('readonly',True)]}),
        'budget_id': fields.many2one('crossovered.budget', 'Budget', required=True, states={'confirm':[('readonly',True)]}),
        'planned_amount': fields.float('Planned Amount', digits=(16,2), required=True, states={'confirm':[('readonly',True)]}),
        'analytic_account_id': fields.many2one('account.analytic.account', 'Analytic Account', required=True, states={'confirm':[('readonly',True)]}),
        'position_id': fields.many2one('account.budget.post', 'Budgetary Position', required=True, states={'confirm':[('readonly',True)]}),
        'date_from': fields.date('Start Date', required=True, states={'confirm':[('readonly',True)]}),
        'date_to': fields.date('End Date', required=True, states={'confirm':[('readonly',True)]}),
        'state' : fields.selection([('draft','Draft'),('confirm','Confirmed')], 'Status', select=True, required=True, readonly=True),
        'company_id': fields.related('budget_id', 'company_id', relation='res.company', type='many2one', string='Company', store=True),
        'responsible_id': fields.related('budget_id', 'creating_user_id', type='many2one', relation='res.users', string='Responsible', store=True)
   }   

    def unlink(self, cr, uid, ids, context=None):
        """Cannot delete a line if the line is confirmed"""
        for line in self.browse(cr, uid, ids):
            if line.state != 'draft':
                raise osv.except_osv(_('Error!'), _('Bevestigde budget detaillijn kan niet verwijderd worden.\nDetaillijn: %s'%(line.name)))
        return super(account_budget_detailline, self).unlink(cr, uid, ids, context=context)

    def default_get(self, cr, uid, fields, context=None):
        """Set dates from last create line"""
        if context is None:
            context = {} 
        result = super(account_budget_detailline, self).default_get(cr, uid, fields, context=context)
        ids = self.search(cr, uid, [])
        if ids:
            line = self.browse(cr, uid, max(ids))
            result['date_from'] = line.date_from
            result['date_to'] = line.date_to
        return result


    _defaults = { 
        'state': 'draft',
    }   

account_budget_detailline()

class wizard_budget_detail_line_confirm(osv.TransientModel):

    _name = 'wizard.budget.detail.line.confirm'

    def lines_confirm(self, cr, uid, ids, context=None):
        for line in self.pool.get('account.budget.detailline').browse(cr, uid, context['active_ids']):
            if line.budget_id.state != 'draft':
                raise osv.except_osv(_('Error!'), _('Detaillijn kan niet bevestigd worden als het gerelateerde budget reeds bevestigd is.\nDetaillijn: %s'%(line.name)))
        return self.pool.get('account.budget.detailline').write(cr, uid, context['active_ids'], {'state':'confirm'})


class wizard_budget_detail_line_draft(osv.TransientModel):

    _name = 'wizard.budget.detail.line.draft'

    def lines_draft(self, cr, uid, ids, context=None):
        lines = self.pool.get('account.budget.detailline').browse(cr, uid, context['active_ids'])
        for line in lines:
            if line.budget_id.state != 'draft':
                raise osv.except_osv(_('Error!'), _('Detaillijn kan niet terug naar voorlopig gezet worden omdat het gerelateerde budget reeds bevestigd is.\nDetaillijn: %s'%(line.name)))
        return self.pool.get('account.budget.detailline').write(cr, uid, context['active_ids'], {'state':'draft'})


class crossovered_budget(osv.osv):

    _inherit = 'crossovered.budget'
  
    def name_get(self, cr, uid, ids, context=None):
        res = []
        budgets =  self.read(cr, uid, ids,['name', 'code'])
        if type(budgets) != type([]):
            budgets = [budgets]
        for r in budgets:
            res.append((r['id'], '[%s] %s' % (r['code'], r['name'])))
        return res  

    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=80):
        if not args:
            args = []
        if context is None:
            context = {}
        ids = []
        if name:
            ids = self.search(cr, user, [('code', 'like', name)] + args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, user, [('name', operator, name)] + args, limit=limit, context=context)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context or {})
        return self.name_get(cr, user, ids, context=context)

    def write(self, cr, uid, ids, vals, context=None):
	# Check if user is part of the budget owner for that specific budget

	for budget in self.browse(cr, uid, ids):
		
		boids = []
		boids.append(budget.creating_user_id.id)
		for bo in budget.creating_user_ids:
			boids.append(bo.id)

		if uid not in boids and uid != 1:
                        raise osv.except_osv(_('Error'),_("Enkel budget verantwoordelijken kunnen budget wijzigen"))

	return super(crossovered_budget, self).write(cr, uid, ids, vals=vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
	# Check if user is the budget owner

	for budget in self.browse(cr, uid, ids):

		if uid != budget.creating_user_id.id and uid != 1:
                        raise osv.except_osv(_('Error'),_("Enkel budget verantwoordelijken kunnen budget verwijderen"))

	return super(crossovered_budget, self).write(cr, uid, ids, vals=vals, context=context)

crossovered_budget()

class wizard_budget_lines_update(osv.TransientModel):

    _name = 'wizard.budget.lines.update'

    def lines_update(self, cr, uid, ids, context=None):
        """Regenerate Budget Lines from the Budget Detail Lines"""

        budget_obj = self.pool.get('crossovered.budget')
        dline_obj = self.pool.get('account.budget.detailline')

        for budget in budget_obj.browse(cr, uid, context['active_ids']):
            if budget.state != 'draft':
                raise osv.except_osv(_('Error!'), _('Lijnen van voorlopige budgetten kunnen niet bijgewerkt worden (%s)'%(budget.name)))

            # Delete existing lines
            del_lines = self.pool.get('crossovered.budget.lines').search(cr, uid, [('crossovered_budget_id','=',budget.id)])
            self.pool.get('crossovered.budget.lines').unlink(cr, uid, del_lines)
            
            # Group detail lines by Budget / Analytic Account / Budgetary Position
            # 1/ Finds all detail lines for that budget
            budget_lines = dline_obj.search(cr, uid, [('budget_id','=',budget.id),('state','=','confirm')], context=context)
            blines_info = dline_obj.read(cr, uid, budget_lines, ['analytic_account_id','position_id','date_from','date_to'], context=context)

            # Generate the groupping key
            dlines_grp = {}
            for dl in blines_info:
                grpkey = str(dl['analytic_account_id'][0]) + str(dl['position_id'][0]) + dl['date_from'] + dl['date_to']
                if grpkey not in dlines_grp:
                    dlines_grp[grpkey] = [dl['id']]
                else:
                    dlines_grp[grpkey].append(dl['id'])

#            # 2/ Group by analytic account
#            dlines_acc = {}
#            for dl in blines_info:
#                if dl['analytic_account_id'][0] not in dlines_acc:
#                    dlines_acc[dl['analytic_account_id'][0]] = [{'id':dl['id'], 'position_id':dl['position_id'][0]}]
#                else:
#                    dlines_acc[dl['analytic_account_id'][0]].append({'id':dl['id'], 'position_id':dl['position_id'][0]})
#
#            # 3/ Group by budgeting position
#            dlines_res = {}
#            for k,v in dlines_acc.iteritems():
#                for l in v:
#                    if (k,l['position_id']) not in dlines_res:
#                        dlines_res[(k,l['position_id'])] = [l['id']]
#                    else:
#                        dlines_res[(k,l['position_id'])].append(l['id'])

#            # Create the Budget lines
#            for blk,blv in dlines_res.iteritems():
#                name = ''
#                date_from = False
#                date_to = False
#                planned_amount = 0.0
#                for bl in dline_obj.browse(cr, uid, blv):
#                    name = name + ' ' + bl.name
#                    budget_id = bl.budget_id.id
#                    analytic_account_id = bl.analytic_account_id.id
#                    planned_amount += bl.planned_amount
#                    position_id = bl.position_id.id
#                    if not date_from or date_from > bl.date_from:
#                        date_from = bl.date_from
#                    if not date_to or date_to < bl.date_from:
#                        date_to = bl.date_to

            # Create the Budget lines
            for blk,blv in dlines_grp.iteritems():
                name = ''
                date_from = False
                date_to = False
                planned_amount = 0.0
                for bl in dline_obj.browse(cr, uid, blv):
                    name = name + ' ' + bl.name
                    budget_id = bl.budget_id.id
                    analytic_account_id = bl.analytic_account_id.id
                    planned_amount += bl.planned_amount
                    position_id = bl.position_id.id
#                    if not date_from or date_from > bl.date_from:
#                        date_from = bl.date_from
#                    if not date_to or date_to < bl.date_from:
#                        date_to = bl.date_to
                    date_from = bl.date_from
                    date_to = bl.date_to
                    company_id = bl.company_id.id

                vals = {
                    'name': name,
                    'crossovered_budget_id': budget_id,
                    'analytic_account_id': analytic_account_id,
                    'general_budget_id': position_id,
                    'planned_amount': planned_amount,
                    'date_from': date_from,
                    'date_to': date_to,
                    'company_id': company_id,
                } 

                self.pool.get('crossovered.budget.lines').create(cr, uid, vals, context=context)

        return True


class account_budget_post(osv.osv):

    _inherit = 'account.budget.post'
  
    def name_get(self, cr, uid, ids, context=None):
        res = []
        budgets =  self.read(cr, uid, ids,['name', 'code'])
        if type(budgets) != type([]):
            budgets = [budgets]
        for r in budgets:
            res.append((r['id'], '[%s] %s' % (r['code'], r['name'])))
        return res  

    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=80):
        if not args:
            args = []
        if context is None:
            context = {}
        ids = []
        if name:
            ids = self.search(cr, user, [('code', 'like', name)] + args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, user, [('name', operator, name)] + args, limit=limit, context=context)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context or {})
        return self.name_get(cr, user, ids, context=context)

    def create(self, cr, uid, vals, context=None):
        
        if 'account_ids' in vals and vals['account_ids']:
            for acc in self.pool.get('account.account').browse(cr, uid, vals['account_ids'][0][2]):
                if acc.budgetary_position_ids:
                    for budg in acc.budgetary_position_ids:
                        if not 'budget_assign_force' in vals or 'budget_assign_force' in vals and not vals['budget_assign_force']:
                            raise osv.except_osv(_('Account already assigned !'), _('De rekening %s is al toegekend aan een andere begroting en kan enkel met 'Force Account Assignation' aangepast worden.'%(acc.code)))

        return super(account_budget_post, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        
        for budget_pos in self.browse(cr, uid, ids):
            if 'account_ids' in vals and vals['account_ids']:
                for acc in self.pool.get('account.account').browse(cr, uid, vals['account_ids'][0][2]):
                    if acc.budgetary_position_ids:
                        for budg in acc.budgetary_position_ids:
                            if budg.id != budget_pos.id and not budget_pos.budget_assign_force:
                                raise osv.except_osv(_('Account already assigned !'), _('De rekening %s is al toegekend aan een andere begroting en kan enkel met 'Force Account Assignation' aangepast worden.'%(acc.code)))
        return super(account_budget_post, self).write(cr, uid, ids, vals, context=context)

    _columns = {
            'budget_assign_force': fields.boolean('Show all accounts for assignmen'),
    }

account_budget_post()


class wizard_account_budget_lines_import(osv.TransientModel):

    _name = "wizard.account.budget.lines.import"

    _columns = { 
        'lines_file': fields.binary('Entry Lines File', required=True),
    }   

    def detail_lines_import(self, cr, uid, ids, context=None):
        """Import journal items from a file"""
        obj = self.browse(cr, uid, ids)[0]

        # Check if financial manager or not
        mod_obj = self.pool.get('ir.model.data')
        model_data_ids = mod_obj.search(cr, uid,[('model', '=', 'res.groups'), ('name', '=', 'group_account_manager')], context=context)
        res_id = mod_obj.read(cr, uid, model_data_ids, fields=['res_id'], context=context)[0]['res_id']
        fin_group = self.pool.get('res.groups').browse(cr, uid, res_id)
        gp_users = [x.id for x in fin_group.users]

        finman = False
        if uid in gp_users:
            finman = True

        #TODO: Replace by tempfile for Windows compatibility
        fname = '/tmp/csv_temp_' + datetime.today().strftime('%Y%m%d%H%M%S') + '.csv'
        fp = open(fname,'w+')
        fp.write(base64.decodestring(obj.lines_file))
        fp.close()
        fp = open(fname,'rU')
        reader = csv.reader(fp, delimiter=";", quoting=csv.QUOTE_NONE)
        entry_vals = []

        for row in reader:
            if reader.line_num <= 1:
                continue

            # Find the company
            #company = self.pool.get('res.users').browse(cr, uid, uid).company_id.id     

            # Find the budget
            budget = False
            if row[0] != "": 
                budgets = self.pool.get('crossovered.budget').search(cr, uid, [('code','=',row[0])]) 
                if budgets:
                    budget = budgets[0]

		    # Check if the user in a budget owner for that specific budget
                    bud = self.pool.get('crossovered.budget').browse(cr, uid, budget) 
		    boids = []
		    boids.append(bud.creating_user_id.id)
	            for bo in bud.creating_user_ids:
			boids.append(bo.id)

#                    if uid != bud.creating_user_id.id and not finman:
                    if uid not in boids and not finman:
                        raise osv.except_osv(_('Error'),_("Enkel verantwoordelijken van budget %s kunnen budget lijnen importeren"%(row[0])))

                else:
                    raise osv.except_osv(_('No budget found !'), _('Geen budget gevonden met code %s'%(row[0])))

            # Find the analytic account
            account = False
            if row[1] != "": 
                accounts = self.pool.get('account.analytic.account').search(cr, uid, [('code','=',row[1])]) 
                if accounts:
                    account = accounts[0]
                else:
                    raise osv.except_osv(_('No analytic account found !'), _('Geen analytische rekening gevonden met code %s'%(row[1])))

            # Find the budgetary position
            position = False
            if row[2] != "": 
                positions = self.pool.get('account.budget.post').search(cr, uid, [('code','=',row[2])]) 
                if positions:
                    position = positions[0]
                else:
                    raise osv.except_osv(_('No analytic account found !'), _('Geen begroting gevonden met code %s'%(row[2])))

            # Get the description
            name = row[3]

            # Get the planned amount
            planned_amount = 0.0
            if row[4] != "": 
                planned_amount = float(row[4].replace(',','.'))
            
            # Get the start date
            date_from = False
            if row[5] != "": 
                df = row[5].split('/')
                date_from = df[2] + '-' + df[1].zfill(2) + '-' + df[0].zfill(2)

            # Get the end date
            date_to = False
            if row[6] != "": 
                dt = row[6].split('/')
                date_to = dt[2] + '-' + dt[1].zfill(2) + '-' + dt[0].zfill(2)

            vals = {
                'budget_id': budget,
                'analytic_account_id': account,
                'position_id': position,
                'name': name,
                'planned_amount': planned_amount,
                'date_from': date_from,
                'date_to': date_to,
            } 

            self.pool.get('account.budget.detailline').create(cr, uid, vals, context=context)

        return True

class account_account(osv.osv):

    _inherit = 'account.account'

    def _budget_assigned(self, cr, uid, ids, field_name, arg, context=None):
        result = {}
        for account in self.browse(cr, uid ,ids):
            result[account.id] = False
            if account.budgetary_position_ids:
                result[account.id] = True
        return result


    _columns = {
            'report_type': fields.related('user_type', 'report_type', type="selection", selection=[('none','/'),
                                      ('income', _('Profit & Loss (Income account)')),
                                      ('expense', _('Profit & Loss (Expense account)')),
                                      ('asset', _('Balance Sheet (Asset account)')),
                                      ('liability', _('Balance Sheet (Liability account)'))], 
                                      string="P&L / BS Category", readonly=True),
            'budgetary_position_ids': fields.many2many('account.budget.post', 'account_budget_rel', 'account_id', 'budget_id', 'Budgetary Positions'),
            'budget_assigned': fields.function(_budget_assigned, type="boolean", string="Assigned to Budgetary Position", store=True, readonly=True),
    }


    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        if context is None:
            context = {} 

        if context.get('from_budget_pos'):
            bpost = self.pool.get('account.budget.post').browse(cr, uid, context['from_budget_pos'])
            if not bpost.budget_assign_force:
                account_ids = self.search(cr, uid, [('budgetary_position_ids','=',False),('company_id','=',bpost.company_id.id)])
                args += [('id','in',account_ids)]

        return super(account_account, self).search(cr, uid, args, offset, limit, order, context, count)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
