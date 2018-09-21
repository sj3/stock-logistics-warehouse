from odoo import api, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    @api.multi
    def get_putaway_locations(self, product):
        self.ensure_one()

        current_location = self
        putaway_locations = []
        while current_location and not putaway_locations:
            if current_location.putaway_strategy_id:
                putaway_locations = current_location.putaway_strategy_id.\
                    get_putaway_locations(product, self)
            current_location = current_location.location_id
        return putaway_locations
