from odoo import models, fields


class StockReplentish(models.TransientModel):
    _name = 'stock.replentish'

    picking_type_id = fields.Many2one(
        comodel_name="stock.picking.type",
        string="Picking Type",
        required=True,
        domain=[('code', '=', 'internal')])

    stock_replentish_lines = fields.One2many(
        comodel_name="stock.replentish.line",
        inverse_name="replentish_id",
        string="Lines"
    )

    def do_compute(self):

        for putaway in self.env['stock.product.putaway.strategy'].search(
                [('fixed_location_id',
                  'child_of',
                  self.picking_type_id.default_location_dest_id.id)]
        ):
            product = putaway.product_product_id
            if not product:
                product = putaway.product_tmpl_id.product_variant_id
            product = product.with_context(
                location=putaway.fixed_location_id.id)

            if product.qty_available < putaway.max_capacity:
                self.env['stock.replentish.line'].create({
                    'replentish_id': self.id,
                    'product_id': product.id,
                    'location_id': putaway.fixed_location_id.id,
                    'qty_current': product.qty_available,
                    'qty_replentish': (putaway.max_capacity -
                                       product.qty_available),
                    'qty_max': putaway.max_capacity,
                })

        module = __name__.split('addons.')[1].split('.')[0]
        result_view = self.env.ref(
            '%s.stock_replentish_view_form_preview' % module)
        return {
            'name': "Replentish",
            'res_id': self.id,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.replentish',
            'view_id': result_view.id,
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    def do_replentish(self):
        replentish_group = self.env['procurement.group'].create({
            'name': 'Replentish'  # TODO
        })

        for line in self.stock_replentish_lines:
            if line.qty_replentish > 0:
                proc = self.env['procurement.order'].create({
                    'warehouse_id': self.picking_type_id.warehouse_id.id,
                    'name': 'replentish',  # TODO
                    'location_id': line.location_id.id,
                    'product_id': line.product_id.id,
                    'product_uom': line.product_id.uom_id.id,
                    'group_id': replentish_group.id,
                    'product_qty': line.qty_replentish,
                })
                print 'loc:', line.location_id, ', proc:', proc.location_id
                proc.run()

        return {}
