from collections import namedtuple

from odoo import api, models, _
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.multi
    def do_recalculate_operations(self):
        return self.with_context(
            recalculate_operations=True).do_prepare_partial()

    def _prepare_pack_ops(self, quants, forced_qties):
        if not self._context.get('recalculate_operations', False):
            return super(StockPicking, self)._prepare_pack_ops(
                quants, forced_qties)

        valid_quants = quants.filtered(lambda quant: quant.qty > 0)
        _Mapping = namedtuple(
            'Mapping',
            ('product', 'package', 'owner', 'location', 'location_dst_id'))

        all_products = valid_quants.mapped('product_id') \
            | self.env['product.product'].browse(p.id for p in forced_qties.keys()) \
            | self.move_lines.mapped('product_id')
        product_to_uom = dict(
            (product.id, product.uom_id) for product in all_products)
        picking_moves = self.move_lines.filtered(
            lambda move: move.state not in ('done', 'cancel'))
        for move in picking_moves:
            # If we encounter an UoM that is smaller than the default
            # UoM or the one already chosen, use the new one instead.
            if move.product_uom != product_to_uom[move.product_id.id] and \
               move.product_uom.factor > product_to_uom[
                   move.product_id.id].factor:
                product_to_uom[move.product_id.id] = move.product_uom
        if len(picking_moves.mapped('location_id')) > 1:
            raise UserError(_('The source location must be the same '
                              'for all the moves of the picking.'))
        if len(picking_moves.mapped('location_dest_id')) > 1:
            raise UserError(_('The destination location must be '
                              'the same for all the moves of the picking.'))

        computed_putaway_locations = dict([
            (product,
             self.location_dest_id.get_putaway_locations(product) + [{
                 'capacity': 0,
                 'max_capacity': 0,
                 'location_id': self.location_dest_id.id
             }])
            for product in all_products
        ])

        pack_operation_values = []

        # find the packages we can move as a whole, create pack
        # operations and mark related quants as done
        # top_lvl_packages = valid_quants._get_top_level_packages(
        #     computed_putaway_locations)
        # for pack in top_lvl_packages:
        #     pack_quants = pack.get_content()
        #     pack_operation_values.append({
        #         'picking_id': self.id,
        #         'package_id': pack.id,
        #         'product_qty': 1.0,
        #         'location_id': pack.location_id.id,
        #         'location_dest_id': computed_putaway_locations[
        #             pack_quants[0].product_id],
        #         'owner_id': pack.owner_id.id,
        #     })
        #     valid_quants -= pack_quants

        # Go through all remaining reserved quants and group by
        # product, package, owner, source location and dest location

        # Lots will go into pack operation lot object
        qtys_grouped = {}
        lots_grouped = {}
        for next_quant in valid_quants:
            quant = next_quant
            while quant:
                new_quant = False
                computed_putaway_location = \
                    computed_putaway_locations[quant.product_id][0]

                if quant.qty > computed_putaway_location['capacity'] \
                   and computed_putaway_location['max_capacity'] != 0:
                    new_quant = quant._quant_split(
                        computed_putaway_location['capacity'])
                    if computed_putaway_location['max_capacity'] != 0:
                        del computed_putaway_locations[quant.product_id][0]

                computed_putaway_location['capacity'] -= quant.qty

                key = _Mapping(
                    quant.product_id,
                    quant.package_id,
                    quant.owner_id,
                    quant.location_id,
                    computed_putaway_location['location_id'])
                qtys_grouped.setdefault(key, 0.0)
                qtys_grouped[key] += quant.qty
                if quant.product_id.tracking != 'none' and quant.lot_id:
                    lots_grouped.setdefault(
                        key, dict()).setdefault(quant.lot_id.id, 0.0)
                    lots_grouped[key][quant.lot_id.id] += quant.qty
                quant = new_quant

        # Do the same for the forced quantities
        # (in cases of force_assign or incomming shipment for example)
        for product, current_qty in forced_qties.items():
            if current_qty <= 0.0:
                continue
            qty = current_qty
            while qty > 0.0:
                this_qty = qty
                computed_putaway_location = \
                    computed_putaway_locations[product][0]

                if this_qty > computed_putaway_location['capacity'] \
                   and computed_putaway_location['capacity'] != 0:
                    this_qty = computed_putaway_location['capacity']
                    if computed_putaway_location['capacity'] != 0:
                        del computed_putaway_locations[product][0]

                computed_putaway_location['capacity'] -= this_qty

                key = _Mapping(
                    product,
                    self.env['stock.quant.package'],
                    self.owner_id,
                    self.location_id,
                    computed_putaway_location['location_id'])
                qtys_grouped.setdefault(key, 0.0)
                qtys_grouped[key] += this_qty
                qty -= this_qty

        # Create the necessary operations for the
        # grouped quants and remaining qtys

        # use it to create operations using the same
        # order as the picking stock moves
        product_id_to_vals = {}

        for mapping, qty in qtys_grouped.items():
            uom = product_to_uom[mapping.product.id]
            val_dict = {
                'picking_id': self.id,
                'product_qty': mapping.product.uom_id._compute_quantity(
                    qty, uom),
                'product_id': mapping.product.id,
                'package_id': mapping.package.id,
                'owner_id': mapping.owner.id,
                'location_id': mapping.location.id,
                'location_dest_id': mapping.location_dst_id,
                'product_uom_id': uom.id,
                'pack_lot_ids': [
                    (0, 0, {
                        'lot_id': lot,
                        'qty': 0.0,
                        'qty_todo': mapping.product.uom_id._compute_quantity(
                            lots_grouped[mapping][lot], uom)
                    }) for lot in lots_grouped.get(mapping, {}).keys()],
            }
            product_id_to_vals.setdefault(
                mapping.product.id, list()).append(val_dict)

        for move in self.move_lines.filtered(
                lambda move: move.state not in ('done', 'cancel')):
            values = product_id_to_vals.pop(move.product_id.id, [])
            pack_operation_values += values

        return pack_operation_values
