from __future__ import annotations

from app.agent.models import Contact, MainInfo, SessionState, Site
from app.agent.state import merge_state


def test_merge_state_overwrites_main_info_and_records_field_meta() -> None:
    state = SessionState(
        session_id="session-merge-1",
        main_info=MainInfo(customerMobile="13800138000"),
    )

    merge_state(
        state,
        {"main_info": {"customerMobile": "13900139000", "providePoints": False}},
        turn_number=2,
        source_text="手机号改成13900139000，不发积分",
    )

    assert state.main_info.customerMobile == "13900139000"
    assert state.main_info.providePoints is False
    assert state.main_info.providePointsRatio == 0.0
    assert state.field_meta["main_info.customerMobile"].source_turn == 2
    assert state.field_meta["main_info.customerMobile"].source_text == "手机号改成13900139000，不发积分"


def test_merge_state_merges_contact_by_name_without_duplicate() -> None:
    state = SessionState(
        session_id="session-merge-2",
        contacts=[Contact(contactName="王磊", position="老板", mobile="13900001111")],
    )

    merge_state(
        state,
        {"contacts": [{"contactName": "王磊", "wechat": "same_as_mobile"}]},
        turn_number=3,
        source_text="王磊微信同手机号",
    )

    assert len(state.contacts) == 1
    assert state.contacts[0].contactName == "王磊"
    assert state.contacts[0].mobile == "13900001111"
    assert state.contacts[0].wechat == "13900001111"
    assert state.contacts[0].isPrimary is True
    assert state.field_meta["contacts[0].wechat"].source_turn == 3


def test_merge_state_resolves_same_as_mobile_after_mobile_arrives_later() -> None:
    state = SessionState(
        session_id="session-merge-2b",
        contacts=[Contact(contactName="王磊", position="老板", wechat="same_as_mobile")],
    )

    merge_state(
        state,
        {"contacts": [{"contactName": "王磊", "mobile": "13900001111"}]},
        turn_number=4,
        source_text="王磊电话13900001111",
    )

    assert len(state.contacts) == 1
    assert state.contacts[0].mobile == "13900001111"
    assert state.contacts[0].wechat == "13900001111"


def test_merge_state_merges_contact_by_unique_position() -> None:
    state = SessionState(
        session_id="session-merge-3",
        contacts=[Contact(position="采购", contactName="刘芳")],
    )

    merge_state(
        state,
        {"contacts": [{"position": "采购", "mobile": "13700002222", "wechat": "lf采购"}]},
        turn_number=4,
        source_text="采购电话13700002222，微信lf采购",
    )

    assert len(state.contacts) == 1
    assert state.contacts[0].contactName == "刘芳"
    assert state.contacts[0].position == "采购"
    assert state.contacts[0].mobile == "13700002222"
    assert state.contacts[0].wechat == "lf采购"


def test_merge_state_appends_new_contact_when_no_match() -> None:
    state = SessionState(
        session_id="session-merge-4",
        contacts=[Contact(contactName="王磊", position="老板", mobile="13900001111")],
    )

    merge_state(
        state,
        {"contacts": [{"contactName": "刘芳", "position": "采购", "mobile": "13700002222"}]},
        turn_number=5,
        source_text="新增采购刘芳，电话13700002222",
    )

    assert len(state.contacts) == 2
    assert state.contacts[1].contactName == "刘芳"
    assert state.contacts[0].isPrimary is True


def test_merge_state_modification_prefers_single_existing_contact_for_mobile_update() -> None:
    state = SessionState(
        session_id="session-merge-5",
        contacts=[Contact(contactName="王磊", position="老板", mobile="13900001111", wechat="13900001111")],
    )

    merge_state(
        state,
        {"contacts": [{"mobile": "18800000001"}]},
        turn_number=6,
        source_text="联系人电话改成18800000001",
    )

    assert len(state.contacts) == 1
    assert state.contacts[0].contactName == "王磊"
    assert state.contacts[0].mobile == "18800000001"


def test_merge_state_modification_prefers_single_existing_site_for_address_update() -> None:
    state = SessionState(
        session_id="session-merge-6",
        sites=[
            Site(
                siteType="store",
                fullAddress="浙江省杭州市西湖区文三路18号",
                provinceName="浙江省",
                cityName="杭州市",
                districtName="西湖区",
                isPrimary=True,
            )
        ],
    )

    merge_state(
        state,
        {
            "sites": [
                {
                    "fullAddress": "浙江省杭州市西湖区金鸡湖大道66号",
                    "provinceName": "浙江省",
                    "cityName": "杭州市",
                    "districtName": "西湖区",
                }
            ]
        },
        turn_number=7,
        source_text="门店地址改到浙江省杭州市西湖区金鸡湖大道66号",
    )

    assert len(state.sites) == 1
    assert state.sites[0].fullAddress == "浙江省杭州市西湖区金鸡湖大道66号"
    assert state.sites[0].provinceName == "浙江省"


def test_merge_state_derives_province_city_district_from_full_address() -> None:
    state = SessionState(session_id="session-merge-7")

    merge_state(
        state,
        {
            "sites": [
                {
                    "fullAddress": "广东省深圳市南山区科技园科苑路15号",
                }
            ]
        },
        turn_number=8,
        source_text="门店地址广东省深圳市南山区科技园科苑路15号",
    )

    assert len(state.sites) == 1
    assert state.sites[0].fullAddress == "广东省深圳市南山区科技园科苑路15号"
    assert state.sites[0].provinceName == "广东省"
    assert state.sites[0].cityName == "深圳市"
    assert state.sites[0].districtName == "南山区"
