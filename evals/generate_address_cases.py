from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "evals" / "cases" / "address_extraction_50.jsonl"


FULL_ADDRESS_CASES = [
    ("浙江省杭州市西湖区文三路18号", "浙江省", "杭州市", "西湖区"),
    ("广东省深圳市南山区科技园科苑路15号", "广东省", "深圳市", "南山区"),
    ("四川省成都市武侯区武兴四路166号西部智谷D区2栋", "四川省", "成都市", "武侯区"),
    ("江苏省苏州市工业园区星湖街218号生物纳米园A3楼", "江苏省", "苏州市", "工业园区"),
    ("湖北省武汉市洪山区珞喻路889号光谷中心花园", "湖北省", "武汉市", "洪山区"),
    ("山东省青岛市市北区延吉路116号万达广场", "山东省", "青岛市", "市北区"),
    ("福建省厦门市思明区湖滨南路258号鸿翔大厦", "福建省", "厦门市", "思明区"),
    ("河南省郑州市金水区花园路39号国贸360", "河南省", "郑州市", "金水区"),
    ("陕西省西安市雁塔区科技路33号高新国际商务中心", "陕西省", "西安市", "雁塔区"),
    ("辽宁省沈阳市铁西区建设东路158号万象汇", "辽宁省", "沈阳市", "铁西区"),
]

MISSING_PROVINCE_CASES = [
    ("杭州市西湖区文三路18号", None, "杭州市", "西湖区"),
    ("深圳市南山区科技园科苑路15号", None, "深圳市", "南山区"),
    ("成都市武侯区武兴四路166号西部智谷D区2栋", None, "成都市", "武侯区"),
    ("苏州市工业园区星湖街218号生物纳米园A3楼", None, "苏州市", "工业园区"),
    ("武汉市洪山区珞喻路889号光谷中心花园", None, "武汉市", "洪山区"),
    ("青岛市市北区延吉路116号万达广场", None, "青岛市", "市北区"),
    ("厦门市思明区湖滨南路258号鸿翔大厦", None, "厦门市", "思明区"),
    ("郑州市金水区花园路39号国贸360", None, "郑州市", "金水区"),
    ("西安市雁塔区科技路33号高新国际商务中心", None, "西安市", "雁塔区"),
    ("沈阳市铁西区建设东路158号万象汇", None, "沈阳市", "铁西区"),
]

MISSING_CITY_CASES = [
    ("浙江省西湖区文三路18号", "浙江省", None, "西湖区"),
    ("广东省南山区科技园科苑路15号", "广东省", None, "南山区"),
    ("四川省武侯区武兴四路166号西部智谷D区2栋", "四川省", None, "武侯区"),
    ("江苏省工业园区星湖街218号生物纳米园A3楼", "江苏省", None, "工业园区"),
    ("湖北省洪山区珞喻路889号光谷中心花园", "湖北省", None, "洪山区"),
    ("山东省市北区延吉路116号万达广场", "山东省", None, "市北区"),
    ("福建省思明区湖滨南路258号鸿翔大厦", "福建省", None, "思明区"),
    ("河南省金水区花园路39号国贸360", "河南省", None, "金水区"),
    ("陕西省雁塔区科技路33号高新国际商务中心", "陕西省", None, "雁塔区"),
    ("辽宁省铁西区建设东路158号万象汇", "辽宁省", None, "铁西区"),
]

MISSING_DISTRICT_CASES = [
    ("浙江省杭州市文三路18号", "浙江省", "杭州市", None),
    ("广东省深圳市科技园科苑路15号", "广东省", "深圳市", None),
    ("四川省成都市武兴四路166号西部智谷D区2栋", "四川省", "成都市", None),
    ("江苏省苏州市星湖街218号生物纳米园A3楼", "江苏省", "苏州市", None),
    ("湖北省武汉市珞喻路889号光谷中心花园", "湖北省", "武汉市", None),
    ("山东省青岛市延吉路116号万达广场", "山东省", "青岛市", None),
    ("福建省厦门市湖滨南路258号鸿翔大厦", "福建省", "厦门市", None),
    ("河南省郑州市花园路39号国贸360", "河南省", "郑州市", None),
    ("陕西省西安市科技路33号高新国际商务中心", "陕西省", "西安市", None),
    ("辽宁省沈阳市建设东路158号万象汇", "辽宁省", "沈阳市", None),
]

MISSING_DETAIL_CASES = [
    ("浙江省杭州市西湖区", "浙江省", "杭州市", "西湖区"),
    ("广东省深圳市南山区", "广东省", "深圳市", "南山区"),
    ("四川省成都市武侯区", "四川省", "成都市", "武侯区"),
    ("江苏省苏州市工业园区", "江苏省", "苏州市", "工业园区"),
    ("湖北省武汉市洪山区", "湖北省", "武汉市", "洪山区"),
    ("山东省青岛市市北区", "山东省", "青岛市", "市北区"),
    ("福建省厦门市思明区", "福建省", "厦门市", "思明区"),
    ("河南省郑州市金水区", "河南省", "郑州市", "金水区"),
    ("陕西省西安市雁塔区", "陕西省", "西安市", "雁塔区"),
    ("辽宁省沈阳市铁西区", "辽宁省", "沈阳市", "铁西区"),
]


SCENE_DEFINITIONS = [
    ("full_address", FULL_ADDRESS_CASES, "门店地址在{address}。"),
    ("missing_province", MISSING_PROVINCE_CASES, "门店位置是{address}。"),
    ("missing_city", MISSING_CITY_CASES, "维修站地址写成{address}。"),
    ("missing_district", MISSING_DISTRICT_CASES, "仓库在{address}。"),
    ("missing_detail", MISSING_DETAIL_CASES, "经营地址是{address}。"),
]


def build_expected_patch(
    *,
    address: str,
    province: str | None,
    city: str | None,
    district: str | None,
) -> dict[str, object]:
    site: dict[str, object] = {"fullAddress": address}
    if province:
        site["provinceName"] = province
    if city:
        site["cityName"] = city
    if district:
        site["districtName"] = district
    return {"sites": [site]}


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for scene_name, rows, template in SCENE_DEFINITIONS:
        for index, (address, province, city, district) in enumerate(rows, start=1):
            payload = {
                "case_id": f"addr_{scene_name}_{index:02d}",
                "scene": scene_name,
                "message": template.format(address=address),
                "expected_patch": build_expected_patch(
                    address=address,
                    province=province,
                    city=city,
                    district=district,
                ),
                "tags": [scene_name, "address"],
            }
            lines.append(json.dumps(payload, ensure_ascii=False))
    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"generated_cases={OUTPUT_PATH}")
    print(f"case_count={len(lines)}")


if __name__ == "__main__":
    main()
