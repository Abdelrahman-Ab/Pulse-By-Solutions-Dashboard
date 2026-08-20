from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from api import data_engine


def build_all(paths: dict, source: str = 'dropbox'):
    started = time.time()
    data_engine.configure_files(paths)

    opportunities = data_engine.load_opportunities()
    if not opportunities:
        raise RuntimeError('List of Opportunities produced no valid opportunities.')

    orderbook = data_engine.load_orderbook()
    if not orderbook:
        raise RuntimeError('Order Book workbook produced no rows.')

    won_matched, won_pending = data_engine.join_awarded(opportunities, orderbook)
    targets = data_engine.load_targets()
    for market in ('Egypt', 'KSA', 'GM', 'Total'):
        if market not in targets:
            raise RuntimeError(f'Target workbook is missing {market}.')

    po_date_map, products, items = data_engine.load_po_dates()
    if not po_date_map:
        raise RuntimeError('Purchase Order Details produced no Purchase Order date mappings.')
    purchase_orders, po_matches = data_engine.load_po(po_date_map)
    if not purchase_orders:
        raise RuntimeError('Purchase Order Summary produced no purchase orders.')

    generated = datetime.now(timezone.utc).isoformat(timespec='seconds')
    meta = {
        'generatedAt': generated,
        'opportunities': len(opportunities),
        'd365OppIdPopulated': sum(1 for x in opportunities if str(x.get('d365Id', '')).strip()),
        'won': sum(1 for x in opportunities if str(x.get('roadmap', '')).lower() == 'won'),
        'wonMatched': won_matched,
        'wonPending': won_pending,
        'orderBookRows': len(orderbook),
        'purchaseOrders': len(purchase_orders),
        'purchaseOrderDateMatches': po_matches,
        'purchaseOrderDateLookupSize': len(po_date_map),
        'roadmapOrder': data_engine.ROADMAP_ORDER,
        'source': source,
        'buildSeconds': round(time.time() - started, 2),
    }

    core_obj = {
        'meta': meta,
        'targets': targets,
        'opportunities': opportunities,
        'orderbook': orderbook,
    }
    po_obj = {
        'meta': meta,
        'purchaseOrders': purchase_orders,
        'products': products,
        'items': items,
    }
    core_raw = json.dumps(core_obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    po_raw = json.dumps(po_obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return core_raw, po_raw, meta
