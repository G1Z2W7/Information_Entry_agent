# 地址字段提取测试报告

- 运行时间：2026-06-04T11:06:55.030430+00:00
- 用例文件：`/workspace/evals/cases/address_extraction_50.jsonl`
- 模型：`deepseek-v4-flash`

## 总体指标

| 指标 | 数值 |
| --- | --- |
| 用例数 | 50 |
| 完全一致率 | 0.56 |
| 字段精确率 | 0.8796 |
| 字段召回率 | 0.9882 |
| 字段 F1 | 0.9307 |
| 平均耗时（秒） | 4.461 |
| 错误用例数 | 0 |

## 分场景指标

| 场景 | 用例数 | 完全一致率 | 精确率 | 召回率 | F1 | 平均耗时（秒） |
| --- | --- | --- | --- | --- | --- | --- |
| full_address | 10 | 1.0 | 1.0 | 1.0 | 1.0 | 3.092 |
| missing_city | 10 | 0.6 | 0.8824 | 1.0 | 0.9375 | 7.077 |
| missing_detail | 10 | 0.9 | 0.95 | 0.95 | 0.95 | 2.919 |
| missing_district | 10 | 0.1 | 0.7692 | 1.0 | 0.8695 | 4.86 |
| missing_province | 10 | 0.2 | 0.7895 | 1.0 | 0.8824 | 4.36 |

## 用例明细

| 用例 | 场景 | 测试语句 | 期望提取 | 最终提取结果 | 完全一致 | 耗时（秒） |
| --- | --- | --- | --- | --- | --- | --- |
| addr_full_address_01 | full_address | 门店地址在浙江省杭州市西湖区文三路18号。 | `{"sites": [{"fullAddress": "浙江省杭州市西湖区文三路18号", "provinceName": "浙江省", "cityName": "杭州市", "districtName": "西湖区"}]}` | `{"sites": [{"fullAddress": "浙江省杭州市西湖区文三路18号", "provinceName": "浙江省", "cityName": "杭州市", "districtName": "西湖区"}]}` | 是 | 3.724 |
| addr_full_address_02 | full_address | 门店地址在广东省深圳市南山区科技园科苑路15号。 | `{"sites": [{"fullAddress": "广东省深圳市南山区科技园科苑路15号", "provinceName": "广东省", "cityName": "深圳市", "districtName": "南山区"}]}` | `{"sites": [{"fullAddress": "广东省深圳市南山区科技园科苑路15号", "provinceName": "广东省", "cityName": "深圳市", "districtName": "南山区"}]}` | 是 | 3.571 |
| addr_full_address_03 | full_address | 门店地址在四川省成都市武侯区武兴四路166号西部智谷D区2栋。 | `{"sites": [{"fullAddress": "四川省成都市武侯区武兴四路166号西部智谷D区2栋", "provinceName": "四川省", "cityName": "成都市", "districtName": "武侯区"}]}` | `{"sites": [{"fullAddress": "四川省成都市武侯区武兴四路166号西部智谷D区2栋", "provinceName": "四川省", "cityName": "成都市", "districtName": "武侯区"}]}` | 是 | 2.84 |
| addr_full_address_04 | full_address | 门店地址在江苏省苏州市工业园区星湖街218号生物纳米园A3楼。 | `{"sites": [{"fullAddress": "江苏省苏州市工业园区星湖街218号生物纳米园A3楼", "provinceName": "江苏省", "cityName": "苏州市", "districtName": "工业园区"}]}` | `{"sites": [{"fullAddress": "江苏省苏州市工业园区星湖街218号生物纳米园A3楼", "provinceName": "江苏省", "cityName": "苏州市", "districtName": "工业园区"}]}` | 是 | 3.758 |
| addr_full_address_05 | full_address | 门店地址在湖北省武汉市洪山区珞喻路889号光谷中心花园。 | `{"sites": [{"fullAddress": "湖北省武汉市洪山区珞喻路889号光谷中心花园", "provinceName": "湖北省", "cityName": "武汉市", "districtName": "洪山区"}]}` | `{"sites": [{"fullAddress": "湖北省武汉市洪山区珞喻路889号光谷中心花园", "provinceName": "湖北省", "cityName": "武汉市", "districtName": "洪山区"}]}` | 是 | 3.039 |
| addr_full_address_06 | full_address | 门店地址在山东省青岛市市北区延吉路116号万达广场。 | `{"sites": [{"fullAddress": "山东省青岛市市北区延吉路116号万达广场", "provinceName": "山东省", "cityName": "青岛市", "districtName": "市北区"}]}` | `{"sites": [{"fullAddress": "山东省青岛市市北区延吉路116号万达广场", "provinceName": "山东省", "cityName": "青岛市", "districtName": "市北区"}]}` | 是 | 2.519 |
| addr_full_address_07 | full_address | 门店地址在福建省厦门市思明区湖滨南路258号鸿翔大厦。 | `{"sites": [{"fullAddress": "福建省厦门市思明区湖滨南路258号鸿翔大厦", "provinceName": "福建省", "cityName": "厦门市", "districtName": "思明区"}]}` | `{"sites": [{"fullAddress": "福建省厦门市思明区湖滨南路258号鸿翔大厦", "provinceName": "福建省", "cityName": "厦门市", "districtName": "思明区"}]}` | 是 | 3.423 |
| addr_full_address_08 | full_address | 门店地址在河南省郑州市金水区花园路39号国贸360。 | `{"sites": [{"fullAddress": "河南省郑州市金水区花园路39号国贸360", "provinceName": "河南省", "cityName": "郑州市", "districtName": "金水区"}]}` | `{"sites": [{"fullAddress": "河南省郑州市金水区花园路39号国贸360", "provinceName": "河南省", "cityName": "郑州市", "districtName": "金水区"}]}` | 是 | 2.585 |
| addr_full_address_09 | full_address | 门店地址在陕西省西安市雁塔区科技路33号高新国际商务中心。 | `{"sites": [{"fullAddress": "陕西省西安市雁塔区科技路33号高新国际商务中心", "provinceName": "陕西省", "cityName": "西安市", "districtName": "雁塔区"}]}` | `{"sites": [{"fullAddress": "陕西省西安市雁塔区科技路33号高新国际商务中心", "provinceName": "陕西省", "cityName": "西安市", "districtName": "雁塔区"}]}` | 是 | 2.849 |
| addr_full_address_10 | full_address | 门店地址在辽宁省沈阳市铁西区建设东路158号万象汇。 | `{"sites": [{"fullAddress": "辽宁省沈阳市铁西区建设东路158号万象汇", "provinceName": "辽宁省", "cityName": "沈阳市", "districtName": "铁西区"}]}` | `{"sites": [{"fullAddress": "辽宁省沈阳市铁西区建设东路158号万象汇", "provinceName": "辽宁省", "cityName": "沈阳市", "districtName": "铁西区"}]}` | 是 | 2.612 |
| addr_missing_province_01 | missing_province | 门店位置是杭州市西湖区文三路18号。 | `{"sites": [{"fullAddress": "杭州市西湖区文三路18号", "cityName": "杭州市", "districtName": "西湖区"}]}` | `{"sites": [{"fullAddress": "杭州市西湖区文三路18号", "cityName": "杭州市", "districtName": "西湖区"}]}` | 是 | 3.943 |
| addr_missing_province_02 | missing_province | 门店位置是深圳市南山区科技园科苑路15号。 | `{"sites": [{"fullAddress": "深圳市南山区科技园科苑路15号", "cityName": "深圳市", "districtName": "南山区"}]}` | `{"sites": [{"fullAddress": "深圳市南山区科技园科苑路15号", "provinceName": "广东省", "cityName": "深圳市", "districtName": "南山区"}]}` | 否 | 3.777 |
| addr_missing_province_03 | missing_province | 门店位置是成都市武侯区武兴四路166号西部智谷D区2栋。 | `{"sites": [{"fullAddress": "成都市武侯区武兴四路166号西部智谷D区2栋", "cityName": "成都市", "districtName": "武侯区"}]}` | `{"sites": [{"fullAddress": "成都市武侯区武兴四路166号西部智谷D区2栋", "provinceName": "四川省", "cityName": "成都市", "districtName": "武侯区"}]}` | 否 | 2.841 |
| addr_missing_province_04 | missing_province | 门店位置是苏州市工业园区星湖街218号生物纳米园A3楼。 | `{"sites": [{"fullAddress": "苏州市工业园区星湖街218号生物纳米园A3楼", "cityName": "苏州市", "districtName": "工业园区"}]}` | `{"sites": [{"fullAddress": "苏州市工业园区星湖街218号生物纳米园A3楼", "provinceName": "江苏省", "cityName": "苏州市", "districtName": "工业园区"}]}` | 否 | 3.519 |
| addr_missing_province_05 | missing_province | 门店位置是武汉市洪山区珞喻路889号光谷中心花园。 | `{"sites": [{"fullAddress": "武汉市洪山区珞喻路889号光谷中心花园", "cityName": "武汉市", "districtName": "洪山区"}]}` | `{"sites": [{"fullAddress": "武汉市洪山区珞喻路889号光谷中心花园", "cityName": "武汉市", "districtName": "洪山区"}]}` | 是 | 4.349 |
| addr_missing_province_06 | missing_province | 门店位置是青岛市市北区延吉路116号万达广场。 | `{"sites": [{"fullAddress": "青岛市市北区延吉路116号万达广场", "cityName": "青岛市", "districtName": "市北区"}]}` | `{"sites": [{"fullAddress": "青岛市市北区延吉路116号万达广场", "provinceName": "山东省", "cityName": "青岛市", "districtName": "市北区"}]}` | 否 | 6.032 |
| addr_missing_province_07 | missing_province | 门店位置是厦门市思明区湖滨南路258号鸿翔大厦。 | `{"sites": [{"fullAddress": "厦门市思明区湖滨南路258号鸿翔大厦", "cityName": "厦门市", "districtName": "思明区"}]}` | `{"sites": [{"fullAddress": "厦门市思明区湖滨南路258号鸿翔大厦", "provinceName": "福建省", "cityName": "厦门市", "districtName": "思明区"}]}` | 否 | 4.872 |
| addr_missing_province_08 | missing_province | 门店位置是郑州市金水区花园路39号国贸360。 | `{"sites": [{"fullAddress": "郑州市金水区花园路39号国贸360", "cityName": "郑州市", "districtName": "金水区"}]}` | `{"sites": [{"fullAddress": "郑州市金水区花园路39号国贸360", "provinceName": "河南省", "cityName": "郑州市", "districtName": "金水区"}]}` | 否 | 5.018 |
| addr_missing_province_09 | missing_province | 门店位置是西安市雁塔区科技路33号高新国际商务中心。 | `{"sites": [{"fullAddress": "西安市雁塔区科技路33号高新国际商务中心", "cityName": "西安市", "districtName": "雁塔区"}]}` | `{"sites": [{"fullAddress": "西安市雁塔区科技路33号高新国际商务中心", "provinceName": "陕西省", "cityName": "西安市", "districtName": "雁塔区"}]}` | 否 | 2.561 |
| addr_missing_province_10 | missing_province | 门店位置是沈阳市铁西区建设东路158号万象汇。 | `{"sites": [{"fullAddress": "沈阳市铁西区建设东路158号万象汇", "cityName": "沈阳市", "districtName": "铁西区"}]}` | `{"sites": [{"fullAddress": "沈阳市铁西区建设东路158号万象汇", "provinceName": "辽宁省", "cityName": "沈阳市", "districtName": "铁西区"}]}` | 否 | 6.684 |
| addr_missing_city_01 | missing_city | 维修站地址写成浙江省西湖区文三路18号。 | `{"sites": [{"fullAddress": "浙江省西湖区文三路18号", "provinceName": "浙江省", "districtName": "西湖区"}]}` | `{"sites": [{"siteType": "维修站", "fullAddress": "浙江省西湖区文三路18号", "provinceName": "浙江省", "districtName": "西湖区"}]}` | 否 | 10.01 |
| addr_missing_city_02 | missing_city | 维修站地址写成广东省南山区科技园科苑路15号。 | `{"sites": [{"fullAddress": "广东省南山区科技园科苑路15号", "provinceName": "广东省", "districtName": "南山区"}]}` | `{"sites": [{"fullAddress": "广东省南山区科技园科苑路15号", "provinceName": "广东省", "districtName": "南山区"}]}` | 是 | 6.561 |
| addr_missing_city_03 | missing_city | 维修站地址写成四川省武侯区武兴四路166号西部智谷D区2栋。 | `{"sites": [{"fullAddress": "四川省武侯区武兴四路166号西部智谷D区2栋", "provinceName": "四川省", "districtName": "武侯区"}]}` | `{"sites": [{"siteType": "维修站", "fullAddress": "四川省武侯区武兴四路166号西部智谷D区2栋", "provinceName": "四川省", "districtName": "武侯区"}]}` | 否 | 8.588 |
| addr_missing_city_04 | missing_city | 维修站地址写成江苏省工业园区星湖街218号生物纳米园A3楼。 | `{"sites": [{"fullAddress": "江苏省工业园区星湖街218号生物纳米园A3楼", "provinceName": "江苏省", "districtName": "工业园区"}]}` | `{"sites": [{"fullAddress": "江苏省工业园区星湖街218号生物纳米园A3楼", "provinceName": "江苏省", "districtName": "工业园区"}]}` | 是 | 5.08 |
| addr_missing_city_05 | missing_city | 维修站地址写成湖北省洪山区珞喻路889号光谷中心花园。 | `{"sites": [{"fullAddress": "湖北省洪山区珞喻路889号光谷中心花园", "provinceName": "湖北省", "districtName": "洪山区"}]}` | `{"sites": [{"fullAddress": "湖北省洪山区珞喻路889号光谷中心花园", "provinceName": "湖北省", "cityName": "武汉市", "districtName": "洪山区"}]}` | 否 | 7.376 |
| addr_missing_city_06 | missing_city | 维修站地址写成山东省市北区延吉路116号万达广场。 | `{"sites": [{"fullAddress": "山东省市北区延吉路116号万达广场", "provinceName": "山东省", "districtName": "市北区"}]}` | `{"sites": [{"fullAddress": "山东省市北区延吉路116号万达广场", "provinceName": "山东省", "cityName": "青岛市", "districtName": "市北区"}]}` | 否 | 9.119 |
| addr_missing_city_07 | missing_city | 维修站地址写成福建省思明区湖滨南路258号鸿翔大厦。 | `{"sites": [{"fullAddress": "福建省思明区湖滨南路258号鸿翔大厦", "provinceName": "福建省", "districtName": "思明区"}]}` | `{"sites": [{"fullAddress": "福建省思明区湖滨南路258号鸿翔大厦", "provinceName": "福建省", "districtName": "思明区"}]}` | 是 | 7.349 |
| addr_missing_city_08 | missing_city | 维修站地址写成河南省金水区花园路39号国贸360。 | `{"sites": [{"fullAddress": "河南省金水区花园路39号国贸360", "provinceName": "河南省", "districtName": "金水区"}]}` | `{"sites": [{"fullAddress": "河南省金水区花园路39号国贸360", "provinceName": "河南省", "districtName": "金水区"}]}` | 是 | 5.397 |
| addr_missing_city_09 | missing_city | 维修站地址写成陕西省雁塔区科技路33号高新国际商务中心。 | `{"sites": [{"fullAddress": "陕西省雁塔区科技路33号高新国际商务中心", "provinceName": "陕西省", "districtName": "雁塔区"}]}` | `{"sites": [{"fullAddress": "陕西省雁塔区科技路33号高新国际商务中心", "provinceName": "陕西省", "districtName": "雁塔区"}]}` | 是 | 6.28 |
| addr_missing_city_10 | missing_city | 维修站地址写成辽宁省铁西区建设东路158号万象汇。 | `{"sites": [{"fullAddress": "辽宁省铁西区建设东路158号万象汇", "provinceName": "辽宁省", "districtName": "铁西区"}]}` | `{"sites": [{"fullAddress": "辽宁省铁西区建设东路158号万象汇", "provinceName": "辽宁省", "districtName": "铁西区"}]}` | 是 | 5.008 |
| addr_missing_district_01 | missing_district | 仓库在浙江省杭州市文三路18号。 | `{"sites": [{"fullAddress": "浙江省杭州市文三路18号", "provinceName": "浙江省", "cityName": "杭州市"}]}` | `{"sites": [{"siteType": "仓库", "fullAddress": "浙江省杭州市文三路18号", "provinceName": "浙江省", "cityName": "杭州市"}]}` | 否 | 4.102 |
| addr_missing_district_02 | missing_district | 仓库在广东省深圳市科技园科苑路15号。 | `{"sites": [{"fullAddress": "广东省深圳市科技园科苑路15号", "provinceName": "广东省", "cityName": "深圳市"}]}` | `{"sites": [{"siteType": "仓库", "fullAddress": "广东省深圳市科技园科苑路15号", "provinceName": "广东省", "cityName": "深圳市"}]}` | 否 | 5.363 |
| addr_missing_district_03 | missing_district | 仓库在四川省成都市武兴四路166号西部智谷D区2栋。 | `{"sites": [{"fullAddress": "四川省成都市武兴四路166号西部智谷D区2栋", "provinceName": "四川省", "cityName": "成都市"}]}` | `{"sites": [{"siteType": "仓库", "fullAddress": "四川省成都市武兴四路166号西部智谷D区2栋", "provinceName": "四川省", "cityName": "成都市"}]}` | 否 | 4.224 |
| addr_missing_district_04 | missing_district | 仓库在江苏省苏州市星湖街218号生物纳米园A3楼。 | `{"sites": [{"fullAddress": "江苏省苏州市星湖街218号生物纳米园A3楼", "provinceName": "江苏省", "cityName": "苏州市"}]}` | `{"sites": [{"fullAddress": "江苏省苏州市星湖街218号生物纳米园A3楼", "provinceName": "江苏省", "cityName": "苏州市"}]}` | 是 | 4.34 |
| addr_missing_district_05 | missing_district | 仓库在湖北省武汉市珞喻路889号光谷中心花园。 | `{"sites": [{"fullAddress": "湖北省武汉市珞喻路889号光谷中心花园", "provinceName": "湖北省", "cityName": "武汉市"}]}` | `{"sites": [{"siteType": "仓库", "fullAddress": "湖北省武汉市珞喻路889号光谷中心花园", "provinceName": "湖北省", "cityName": "武汉市"}]}` | 否 | 4.408 |
| addr_missing_district_06 | missing_district | 仓库在山东省青岛市延吉路116号万达广场。 | `{"sites": [{"fullAddress": "山东省青岛市延吉路116号万达广场", "provinceName": "山东省", "cityName": "青岛市"}]}` | `{"sites": [{"siteType": "仓库", "fullAddress": "山东省青岛市延吉路116号万达广场", "provinceName": "山东省", "cityName": "青岛市"}]}` | 否 | 6.517 |
| addr_missing_district_07 | missing_district | 仓库在福建省厦门市湖滨南路258号鸿翔大厦。 | `{"sites": [{"fullAddress": "福建省厦门市湖滨南路258号鸿翔大厦", "provinceName": "福建省", "cityName": "厦门市"}]}` | `{"sites": [{"siteType": "仓库", "fullAddress": "福建省厦门市湖滨南路258号鸿翔大厦", "provinceName": "福建省", "cityName": "厦门市"}]}` | 否 | 4.804 |
| addr_missing_district_08 | missing_district | 仓库在河南省郑州市花园路39号国贸360。 | `{"sites": [{"fullAddress": "河南省郑州市花园路39号国贸360", "provinceName": "河南省", "cityName": "郑州市"}]}` | `{"sites": [{"siteType": "仓库", "fullAddress": "河南省郑州市花园路39号国贸360", "provinceName": "河南省", "cityName": "郑州市"}]}` | 否 | 5.17 |
| addr_missing_district_09 | missing_district | 仓库在陕西省西安市科技路33号高新国际商务中心。 | `{"sites": [{"fullAddress": "陕西省西安市科技路33号高新国际商务中心", "provinceName": "陕西省", "cityName": "西安市"}]}` | `{"sites": [{"siteType": "仓库", "fullAddress": "陕西省西安市科技路33号高新国际商务中心", "provinceName": "陕西省", "cityName": "西安市"}]}` | 否 | 5.063 |
| addr_missing_district_10 | missing_district | 仓库在辽宁省沈阳市建设东路158号万象汇。 | `{"sites": [{"fullAddress": "辽宁省沈阳市建设东路158号万象汇", "provinceName": "辽宁省", "cityName": "沈阳市"}]}` | `{"sites": [{"siteType": "仓库", "fullAddress": "辽宁省沈阳市建设东路158号万象汇", "provinceName": "辽宁省", "cityName": "沈阳市"}]}` | 否 | 4.611 |
| addr_missing_detail_01 | missing_detail | 经营地址是浙江省杭州市西湖区。 | `{"sites": [{"fullAddress": "浙江省杭州市西湖区", "provinceName": "浙江省", "cityName": "杭州市", "districtName": "西湖区"}]}` | `{"sites": [{"fullAddress": "浙江省杭州市西湖区", "provinceName": "浙江省", "cityName": "杭州市", "districtName": "西湖区"}]}` | 是 | 3.264 |
| addr_missing_detail_02 | missing_detail | 经营地址是广东省深圳市南山区。 | `{"sites": [{"fullAddress": "广东省深圳市南山区", "provinceName": "广东省", "cityName": "深圳市", "districtName": "南山区"}]}` | `{"sites": [{"fullAddress": "广东省深圳市南山区", "provinceName": "广东省", "cityName": "深圳市", "districtName": "南山区"}]}` | 是 | 2.331 |
| addr_missing_detail_03 | missing_detail | 经营地址是四川省成都市武侯区。 | `{"sites": [{"fullAddress": "四川省成都市武侯区", "provinceName": "四川省", "cityName": "成都市", "districtName": "武侯区"}]}` | `{"sites": [{"fullAddress": "四川省成都市武侯区", "provinceName": "四川省", "cityName": "成都市", "districtName": "武侯区"}]}` | 是 | 3.245 |
| addr_missing_detail_04 | missing_detail | 经营地址是江苏省苏州市工业园区。 | `{"sites": [{"fullAddress": "江苏省苏州市工业园区", "provinceName": "江苏省", "cityName": "苏州市", "districtName": "工业园区"}]}` | `{"sites": [{"fullAddress": "江苏省苏州市工业园区", "provinceName": "江苏省", "cityName": "苏州市", "districtName": "工业园区"}]}` | 是 | 2.759 |
| addr_missing_detail_05 | missing_detail | 经营地址是湖北省武汉市洪山区。 | `{"sites": [{"fullAddress": "湖北省武汉市洪山区", "provinceName": "湖北省", "cityName": "武汉市", "districtName": "洪山区"}]}` | `{"sites": [{"fullAddress": "湖北省武汉市洪山区", "provinceName": "湖北省", "cityName": "武汉市", "districtName": "洪山区"}]}` | 是 | 3.66 |
| addr_missing_detail_06 | missing_detail | 经营地址是山东省青岛市市北区。 | `{"sites": [{"fullAddress": "山东省青岛市市北区", "provinceName": "山东省", "cityName": "青岛市", "districtName": "市北区"}]}` | `{"sites": [{"fullAddress": "山东省青岛市市北区", "provinceName": "山东省", "cityName": "青岛市", "districtName": "市北区"}]}` | 是 | 2.782 |
| addr_missing_detail_07 | missing_detail | 经营地址是福建省厦门市思明区。 | `{"sites": [{"fullAddress": "福建省厦门市思明区", "provinceName": "福建省", "cityName": "厦门市", "districtName": "思明区"}]}` | `{"sites": [{"fullAddress": "福建省厦门市思明区", "provinceName": "福建", "cityName": "厦门", "districtName": "思明区"}]}` | 否 | 2.643 |
| addr_missing_detail_08 | missing_detail | 经营地址是河南省郑州市金水区。 | `{"sites": [{"fullAddress": "河南省郑州市金水区", "provinceName": "河南省", "cityName": "郑州市", "districtName": "金水区"}]}` | `{"sites": [{"fullAddress": "河南省郑州市金水区", "provinceName": "河南省", "cityName": "郑州市", "districtName": "金水区"}]}` | 是 | 3.184 |
| addr_missing_detail_09 | missing_detail | 经营地址是陕西省西安市雁塔区。 | `{"sites": [{"fullAddress": "陕西省西安市雁塔区", "provinceName": "陕西省", "cityName": "西安市", "districtName": "雁塔区"}]}` | `{"sites": [{"fullAddress": "陕西省西安市雁塔区", "provinceName": "陕西省", "cityName": "西安市", "districtName": "雁塔区"}]}` | 是 | 2.758 |
| addr_missing_detail_10 | missing_detail | 经营地址是辽宁省沈阳市铁西区。 | `{"sites": [{"fullAddress": "辽宁省沈阳市铁西区", "provinceName": "辽宁省", "cityName": "沈阳市", "districtName": "铁西区"}]}` | `{"sites": [{"fullAddress": "辽宁省沈阳市铁西区", "provinceName": "辽宁省", "cityName": "沈阳市", "districtName": "铁西区"}]}` | 是 | 2.561 |
