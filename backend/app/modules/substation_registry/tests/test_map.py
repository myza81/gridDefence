"""Substation Registry map projection (Phase E.1).

Verifies the read-only geographic projection: it uses the authoritative
Substation coordinate, classifies present/missing, counts mapped vs missing,
and honours the same filters as the list — never deriving or inferring a
coordinate.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.substation_registry.service import SubstationService
from app.modules.substation_registry.tests.conftest import ReferenceIds


def _create(
    service: SubstationService,
    ref: ReferenceIds,
    actor_user_id: uuid.UUID,
    *,
    mnemonic: str,
    name: str,
    latitude: float | None,
    longitude: float | None,
) -> None:
    service.create_substation(
        mnemonic=mnemonic,
        official_name=name,
        region_id=ref.region_id,
        gm_zone_id=ref.gm_zone_id,
        state_id=ref.state_id,
        grid_owner_id=ref.grid_owner_id,
        operational_status_id=ref.status_id_by_code["ACTIVE"],
        psse_bus_number=None,
        latitude=latitude,
        longitude=longitude,
        commissioned_date=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )


def test_projection_classifies_coordinates_and_counts(
    db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
) -> None:
    service = SubstationService(db_session)
    _create(service, reference_ids, actor_user_id, mnemonic="ABBA", name="A Famosa", latitude=2.430870, longitude=102.280495)
    _create(service, reference_ids, actor_user_id, mnemonic="AFMS", name="Ayer Molek", latitude=None, longitude=None)
    db_session.commit()

    features, mapped, missing = service.list_map_features()

    assert mapped == 1
    assert missing == 1
    assert len(features) == 2

    by_mnemonic = {f.mnemonic: f for f in features}
    assert by_mnemonic["ABBA"].coordinate_status == "present"
    assert by_mnemonic["ABBA"].latitude == 2.430870
    assert by_mnemonic["ABBA"].longitude == 102.280495
    # The projection carries compact classification, never the full ORM object.
    assert by_mnemonic["ABBA"].state_id == reference_ids.state_id
    assert by_mnemonic["AFMS"].coordinate_status == "missing"
    assert by_mnemonic["AFMS"].latitude is None
    assert by_mnemonic["AFMS"].longitude is None


def test_projection_honours_the_shared_filters(
    db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
) -> None:
    service = SubstationService(db_session)
    _create(service, reference_ids, actor_user_id, mnemonic="ABBA", name="A Famosa", latitude=2.43, longitude=102.28)
    _create(service, reference_ids, actor_user_id, mnemonic="BNTG", name="Bentong", latitude=3.52, longitude=101.91)
    db_session.commit()

    # Search matches the same fields (mnemonic/name) as the list endpoint.
    features, mapped, missing = service.list_map_features(search="ABBA")
    assert {f.mnemonic for f in features} == {"ABBA"}
    assert mapped == 1 and missing == 0

    # Lifecycle filter (operational_status_id) — a non-matching status yields none.
    decommissioned = reference_ids.status_id_by_code["DECOMMISSIONED"]
    features, mapped, missing = service.list_map_features(operational_status_id=decommissioned)
    assert features == []
    assert mapped == 0 and missing == 0
