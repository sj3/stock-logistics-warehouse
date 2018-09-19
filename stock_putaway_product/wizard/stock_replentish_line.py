from odoo import models, fields


class StockReplentishLine(models.TransientModel):
    _name = 'stock.replentish.line'

    replentish_id = fields.Many2one(
        comodel_name='stock.replentish'
    )

    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
    )

    qty_replentish = fields.Integer(
        string="Quantity"
    )

    qty_current = fields.Integer(
        string="Current Stock"
    )

    qty_max = fields.Integer(
        string="Max Stock"
    )

    location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Location",
    )
