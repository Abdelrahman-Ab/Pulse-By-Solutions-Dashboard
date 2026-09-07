from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from api import data_engine


class DatasetError(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


def _run(stage, fn, *args):
    try:
        return fn(*args)
    except DatasetError:
        raise
    except Exception as e:
        raise DatasetError(stage, str(e)) from e


def _guard_count(name: str, current: int, previous: int | None):
    """Reject obviously suspicious parser/source collapses instead of publishing bad data.

    This is deliberately broad: normal business changes pass, while a workbook suddenly
    parsing to only a tiny fraction of yesterday's rows is treated as schema/source drift.
    """
    if not previous or previous < 20:
        return
    low = max(1, int(previous * 0.20))
    high = max(previous + 1000, int(previous * 6.0))
    if current < low:
        raise DatasetError(
            f'validate:{name}',
            f'{name} row count changed from {previous} to {current}, which is suspiciously low. '
            'The previous dashboard snapshot was kept unchanged.'
        )
    if current > high:
        raise DatasetError(
            f'validate:{name}',
            f'{name} row count changed from {previous} to {current}, which is suspiciously high. '
            'The previous dashboard snapshot was kept unchanged.'
        )


def build_all(paths: dict, source: str = 'dropbox', previous_meta: dict | None = None):
    started = time.time()
    data_engine.configure_files(paths)
    previous_meta = previous_meta or {}

    opportunities = _run('process:opportunities', data_engine.load_opportunities)
    if not opportunities:
        raise DatasetError('process:opportunities', 'List of Opportunities produced no valid opportunities.')
    _guard_count('opportunities', len(opportunities), previous_meta.get('opportunities'))

    orderbook = _run('process:orderbook', data_engine.load_orderbook)
    if not orderbook:
        raise DatasetError('process:orderbook', 'Order Book workbook produced no rows.')
    _guard_count('orderBookRows', len(orderbook), previous_meta.get('orderBookRows'))

    won_matched, won_pending = _run('process:award-join', data_engine.join_awarded, opportunities, orderbook)

    targets = _run('process:targets', data_engine.load_targets)
    for market in ('Egypt', 'KSA', 'GM', 'Total'):
        if market not in targets:
            raise DatasetError('process:targets', f'Target workbook is missing {market}.')

    po_date_map, products, items = _run('process:po-details', data_engine.load_po_dates)
    if not po_date_map:
        raise DatasetError('process:po-details', 'Purchase Order Details produced no Purchase Order date mappings.')

    purchase_orders, po_matches = _run('process:po-summary', data_engine.load_po, po_date_map)
    if not purchase_orders:
        raise DatasetError('process:po-summary', 'Purchase Order Summary produced no purchase orders.')
    _guard_count('purchaseOrders', len(purchase_orders), previous_meta.get('purchaseOrders'))

    # Enrich Order Book rows with Vendor / Partner relationships from Purchase Order Summary.
    # Contract ID is the approved join key. Keep arrays so one contract can correctly retain
    # multiple vendors/partners without duplicating and therefore over-counting OB value.
    contract_parties = {}
    for po in purchase_orders:
        cid = data_engine.nid(po.get('contractId'))
        if not cid:
            continue
        bucket = contract_parties.setdefault(cid, {'vendors': set(), 'partners': set()})
        vendor = data_engine.clean(po.get('vendor'))
        partner = data_engine.clean(po.get('partnerName'))
        if vendor and vendor.lower() not in ('unassigned','none','nan'):
            bucket['vendors'].add(vendor)
        if partner and partner.lower() not in ('unassigned','none','nan'):
            bucket['partners'].add(partner)
    for row in orderbook:
        rel = contract_parties.get(data_engine.nid(row.get('contractId')), {'vendors': set(), 'partners': set()})
        row['vendorName'] = sorted(rel['vendors'], key=str.casefold)
        row['partnerName'] = sorted(rel['partners'], key=str.casefold)

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
        'pipelineVersion': 'orderbook-analysis-local-v1',
    }

    # These checks catch a parser that technically emitted rows but lost critical columns.
    meta['roadmapPopulated'] = sum(1 for x in opportunities if str(x.get('roadmap', '')).strip().lower() not in ('', 'unassigned', 'none', 'nan'))
    meta['roadmapCoverage'] = round(meta['roadmapPopulated'] / max(1, meta['opportunities']), 4)

    id_rate = meta['d365OppIdPopulated'] / max(1, meta['opportunities'])
    prev_id_rate = (previous_meta.get('d365OppIdPopulated', 0) / max(1, previous_meta.get('opportunities', 0))) if previous_meta.get('opportunities') else None
    if prev_id_rate is not None and prev_id_rate > 0.5 and id_rate < 0.10:
        raise DatasetError(
            'validate:opportunities-schema',
            f'D365 Opp ID coverage dropped from {prev_id_rate:.0%} to {id_rate:.0%}. '
            'This looks like an Excel header/schema change, so the previous snapshot was kept.'
        )

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
