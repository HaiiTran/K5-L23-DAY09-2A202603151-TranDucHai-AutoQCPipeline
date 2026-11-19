# Báo cáo Day 09 — <Họ và tên>, <MSHV>

> Mỗi ý trả lời bằng **số lấy từ `submission/reports/`**, kèm mẫu số. Cả báo cáo ~1–2 trang.

## 1. Kết luận trước
Pipeline kết luận **Release / Hold / Rework**? Bao nhiêu ảnh vào, bao nhiêu ảnh ra dataset? Lý do chính (1–3 câu).
- Pipeline kết luận Hold. Đầu vào có 193/224 ảnh và loại 31/224 ảnh; đầu ra 193 ảnh dataset. Không còn lỗi bắt buộc nhưng còn cảnh báo trên 34 ảnh (17,62%), cao hơn ngưỡng Hold 10%.

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| LEAK_TEST | 11 | Máy | Trùng ảnh kho test/val; bị loại trước QC |
| DUP_IMAGE_EXACT | 8 | Máy | Ảnh trùng, bị loại trước QC |
| DUP_IMAGE_NEAR | 7 | Máy | Ảnh gần trùng, bị loại trước QC |
| CORRUPT_IMAGE | 2 | Máy |  Ảnh lỗi, bị loại trước QC |
| BAD_SIZE | 3 | Máy |  Ảnh quá nhỏ, bị loại trước QC |
| BAD_FORMAT | 3| Máy | Xóa nhãn sai định dạng |
| BAD_CLASS_ID | 6 | Máy | Xóa dòng có id ngoài khoảng|
| BOX_ZERO | 4 | Máy | Xóa dòng có chiều cao/rộng = 0|
| BOX_OUT_OF_IMAGE | 8 | Máy | Box tràn khỏi ảnh|
| DUP_BOX | 7 | Máy | Box trùng với box cùng lớp ở dòng trước|
| BAD_CLASS_NAME | 2 | Máy | Nhãn có tên lớp lạ |
| MISSING_LABEL_FILE | 6 | Người | ảnh không có file nhãn |
| POSSIBLE_MISSING | 53 | Người | phát hiện vật thể nhưng không có box nhãn khớp |
| POSSIBLE_FALSE_POS | 28 | Người | box nhãn không khớp dự đoán model |
| POSSIBLE_LOOSE_BOX | 27| Người | box cùng lớp có thể bị lỏng/lệch |
| POSSIBLE_WRONG_CLASS | 17 | Người | box nhãn khớp vị trí nhưng khác lớp với dự đoán |
| EMPTY_LABEL | 11 | Người | file nhãn bị rỗng |
| BOX_TINY | 6 | Người | cạnh ngắn của box nhỏ hơn 12 px |
| BOX_HUGE | 3 | Người | box chiếm diện tích quá lớn của ảnh |
| CLASS_RARE | 4 | Người | class có quá ít box |

vì sao `05_review_queue.csv` xếp ảnh đầu hàng như vậy? Với ngân sách 80 ảnh, người xem được bao nhiêu lỗi ngữ nghĩa?
- `05_review_queue.csv` xếp ảnh theo priority giảm dần cùng với số cảnh báo theo loại (ví dụ: ảnh đầu hàng `img_0020` có priority 11.524 vì mang các mã FIXED_DROP_LINE, POSSIBLE_MISSING và POSSIBLE_WRONG_CLASS). Với ngân sách 80 ảnh có thể xem được 88 lỗi ngữ nghĩa.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 16 | DUP_IMAGE_EXACT: 1.00 / 0.50 → 1.00 / 0.83. </br> DUP_IMAGE_EXACT: giữ nguyên 1.00 / 1.00 | Ngưỡng này giảm tỷ lệ bỏ sót; ngưỡng cao hơn có thể gộp nhầm ảnh khác nhau. |
| `second_opinion.conf` | 0.25 | 0.6 | WRONG_CLASS: 0.56 / 0.83 → 0.62 / 0.83 - MISSING: 0.50 / 1.00 → 0.57 / 1.00 - LOOSE_BOX: 0.29 / 0.40 → 0.20 / 0.20 - FALSE_POS: 0.31 / 1.00 → 0.31 / 1.00 | Ở 0.6, precision wrong class và missing tăng còn recall của hai nhóm này không đổi. Recall của loose box giảm. |

**một chỗ calibration có thể đánh lừa bạn**, kèm bằng chứng từ dữ liệu của bạn (vd. mở xem vài cặp ảnh bị cho là trùng; số ảnh bị loại ở bước 1 có hợp lý không?).
- Một điểm calibration có thể đánh lừa: mẫu quá nhỏ - với phash_dist=16, kết quả precision 1.00 (5/5) nhưng recall chỉ 0.83 (5/6). Chỉ một lỗi bị bỏ sót làm recall thay đổi.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
(a) chứng minh gate chặn đúng: chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt nên ảnh thiếu file nhãn còn nguyên), chỉ ra kết luận **Rework**, mã thoát 20 và việc **không xuất** dataset. (Đừng sửa tay `work/run/ds`: pipeline dựng lại thư mục này từ raw mỗi lần chạy.) 
- Khi chạy với budget=0, pipeline nhận 193/224 ảnh và loại 31/224. Vì không có người gán nhãn nên vẫn còn 6 lỗi bắt buộc thuộc MISSING_LABEL_FILE sau vòng sửa, đây là nguyên nhân để gate đưa ra kết luận Rework. 
(b) ≥ 2 điểm mù có bằng chứng (box lỏng nhẹ, nhầm lớp mà model lớn cũng nhầm, ảnh trùng biến đổi mạnh…).
- `duplicates.phash_dist=16`: check near-duplicate, kết quả đưa ra precision = 1.00 nhưng recall = 0.83, bắt được 5/6 lỗi chèn và bỏ sót 1 lỗi.
- `second_opinion.conf=0.6`: POSSIBLE_LOOSE_BOX đạt precision 0.20 và recall 0.20, chỉ bắt được 1/5, bỏ sót 4 lỗi box lỏng.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa train: ghi "chưa chạy" và lý do, rồi bỏ qua phần còn lại của mục này. Nếu đã train: dán bảng từ `submission/results/comparison.md` (model, epoch, seed, số ảnh train mỗi biến thể).

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 193 | 2 | 0.729 ± 0.002 | 0.500 ± 0.000 | 0.794 ± 0.028 | 0.619 ± 0.005 |

Chênh mAP50 (clean − raw) = **+0.004**.

chênh mAP50 (clean − raw) so với **độ lệch chuẩn giữa các seed**; kết luận **trung thực** (nằm trong nhiễu thì nói là chưa kết luận được); ≥ 2 giả thuyết giải thích (ảnh trùng/rò rỉ test trong `raw`, nhãn máy còn lại trong `clean`, test chỉ 100 ảnh…) và cách kiểm.
- độ lệch mAP50 bằng 2x-độ lệch clean(0.002) và lớn hơn độ lệch raw. Với độ lệch được ước tính từ lần chạy ở mức rất tối thiểu và tập test chỉ hơn 100 ảnh, không thể kết luận được là clean sẽ sạch hơn raw. 
- Giả thuyết và cách kiểm tra:
    - Raw có ảnh trùng hoặc rò rỉ sang test: `01_intake.csv` ghi nhận 11 ảnh LEAK_TEST và 15 ảnh trùng chính xác/gần đúng trên 224 ảnh. Kiểm tra các cặp bằng hash và chạy lại phép so sánh sau khi loại ảnh trùng/rò rỉ.
    - Tập test nhỏ làm kết quả dao động: đánh giá hiện dựa trên 100 ảnh test. Lặp lại với thêm seed và, nếu có thể, một tập đánh giá lớn hơn để xem chênh lệch có ổn định không.

## 6. Quyết định và ghi chú AI
(a) quyết định cuối; nếu Hold/Rework cần làm gì để thành Release? 
- quyết định cuối là Hold. Cần xử lý và xác minh ít nhất 15 ảnh trong 34 ảnh bị gắn cờ, đồng thời rà soát để không còn lỗi bắt buộc.
(b) Dùng AI viết code? Ghi 3 dòng: prompt chính, cách bạn kiểm code AI, 1 lần AI sai. Không dùng: ghi "không dùng".
- prompt chính: nhờ AI hoàn thiện code label_format, gate, autofix, second_opinion theo docstring và bao quát ca biên. Không hoàn thiện code chỉ để pass file test. 
- đối chiếu docstring và unit tests
- AI thiếu: kiểm tra ngưỡng Hold bị thiếu, không phải số, không hữu hạn hoặc ngoài 0–1 thì báo lỗi cấu hình rõ ràng. Chuẩn hóa image_stems thành tập hợp để mẫu số không đếm trùng ảnh.

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
