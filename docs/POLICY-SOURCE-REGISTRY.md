# Policy source registry

The registry is the allow-list for policy ingestion. Each source must have an
owner, version, effective date, retrieval date, URL and hash.

| Source set | Status checked 2026-07-25 | Use | Ingestion rule |
| --- | --- | --- | --- |
| Law 32/2024/QH15 on Credit Institutions plus Laws 43/2024/QH15 and 96/2025/QH15 | The base law is partly superseded; Law 96/2025 is effective from 2025-10-15. | Credit-activity principles, borrower obligations and secured/unsecured form. | Ingest a reviewed consolidated snapshot, not the base law alone. |
| Circular 39/2016/TT-NHNN plus Circulars 06/2023, 12/2024 and 52/2025 | The base circular is partly superseded; Circular 52/2025 is effective from 2025-12-25. | Lending documentation and process context. | Resolve amendments and corrections before chunking. |
| Law 91/2025/QH15 and Decree 356/2025/NĐ-CP on personal data protection | Both are effective from 2026-01-01. Decree 13/2023/NĐ-CP is no longer effective. | Data purpose, minimization, consent/legal basis and data-subject controls. | Exclude Decree 13 from the active namespace; retain only as historical material if needed. |
| Public bank product terms | Time-sensitive and bank-specific. | Product eligibility and document list. | Record issuing bank, publication/effective date and archive snapshot. |
| Synthetic underwriting profile | Demo-only. | Thresholds and test fixtures. | Label `UNDERWRITING_POLICY` and `synthetic: true`. |

Official starting points:

- [Law 32/2024/QH15](https://vbpl.vn/bonoivu/Pages/vbpq-toanvan.aspx?ItemID=166170)
- [Law 96/2025/QH15 amendment](https://vbpl.vn/ninhbinh/Pages/vbpq-toanvan.aspx?ItemID=179292)
- [Circular 39/2016/TT-NHNN source and history](https://vbpl.vn/TW/Pages/vbpq-van-ban-goc.aspx?ItemID=118230)
- [Circular 12/2024/TT-NHNN amendment](https://vbpl.vn/TW/Pages/vbpq-thuoctinh.aspx?ItemID=167991)
- [Circular 52/2025/TT-NHNN amendment](https://vbpl.vn/TW/Pages/vbpq-thuoctinh.aspx?ItemID=185228)
- [Law 91/2025/QH15 on personal data protection](https://vbpl.vn/bokhoahoccongnghe/Pages/vbpq-thuoctinh.aspx?ItemID=179252)
- [Decree 356/2025/NĐ-CP](https://vbpl.vn/bocongan/Pages/vbpq-toanvan.aspx?ItemID=187276)

The registry is not a legal opinion. A production deployment needs a
compliance owner to review source currency and jurisdiction.
