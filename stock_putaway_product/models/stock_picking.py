from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.multi
    def do_recalculate_operations(self):
        import pdb
        pdb.set_trace()

        return {}
