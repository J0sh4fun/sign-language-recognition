# Nhập Morse bằng ngón tay

Ứng dụng Python cục bộ cho Windows. Webcam theo dõi một bàn tay và chuyển hai động tác chụm ngón thành A–Z, 0–9 và khoảng trắng. Khung hình chỉ được xử lý trong bộ nhớ.

## Chạy trên Windows

### Bố cục dự án

```text
morse_input/    Mã Python của ứng dụng, bộ giải mã và quy trình huấn luyện
tests/          Kiểm thử bộ giải mã, phím tắt và quy trình năm phiên
config/         Cấu hình thời gian giữ, nhả, chốt chữ và cách từ
assets/         Mô hình Hand Landmarker dùng để lấy điểm bàn tay
results/        Kết quả nghiệm thu prototype bằng webcam
personal-data/  Dữ liệu phiên cá nhân, mô hình đã học và báo cáo (tạo khi thu)
```

Tại thư mục gốc, `app.py` mở ứng dụng, `experiment.py` điều khiển quy trình năm phiên, `acceptance.py` mở buổi nghiệm thu một người và `trials.py` tạo hoặc chấm phiếu CSV.

### Khởi động

Trong PowerShell tại thư mục dự án, chạy lệnh cuối nếu đã có môi trường `.venv`. Trên máy mới, chạy lần lượt cả ba lệnh với Python 3.13 x64 có Tkinter.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python app.py
```

Nếu máy có nhiều webcam, dùng `app.py --camera 1`. Nếu mở camera thất bại, kiểm tra chỉ số camera, quyền camera cho ứng dụng desktop trong Windows và ứng dụng khác đang giữ webcam.

## Nhập thử

1. Đặt lòng bàn tay hướng về webcam, giữ cả ba đầu ngón trong khung. Làm theo ba tư thế trên màn hình. Khi đã đặt đúng từng tư thế, nhấn **Space** rồi giữ yên một giây. Nếu mẫu chồng lấn, xoay tay để các đầu ngón hiện tách biệt rồi thu lại.
2. Tách ngón đến khi thấy **Sẵn sàng**. Chụm cái–trỏ để nhập dấu chấm, cái–giữa để nhập dấu gạch. Giữ 150 ms, thấy dấu xuất hiện rồi tách cả hai cặp ít nhất 100 ms trước dấu tiếp theo.
3. Nghỉ một giây để chốt chữ. Nghỉ tổng cộng 2,5 giây để cách từ. Khoảng trắng hiện khi chữ của từ tiếp theo được chốt. Sau khi mất dấu, tách ngón để tiếp tục.
4. Thử **SOS 2026** theo bảng dưới. Nghỉ ngắn giữa các dấu trong một ô, nghỉ chốt chữ khi sang ô tiếp theo, nghỉ cách từ sau chữ S thứ hai.

| S | O | S | 2 | 0 | 2 | 6 |
|---|---|---|---|---|---|---|
| `...` | `---` | `...` | `..---` | `-----` | `..---` | `-....` |

Sau hiệu chuẩn, **Space** hoặc **Backspace** xóa một dấu đang nhập. Nếu chuỗi dấu trống, phím sẽ xóa ký tự đã chốt gần nhất. Trong ứng dụng nghiệm thu một người, hai phím dùng được ở lượt làm quen và bị khóa trong lượt đo để ghi kết quả trước sửa. **Esc** đóng ứng dụng. Chỉnh bốn mốc thời gian trong [config/config.json](config/config.json) (mili giây) rồi mở lại ứng dụng.

## Kiểm tra kỹ thuật

```powershell
.\.venv\Scripts\python -m unittest -v
```

Đã thử trên Windows với Python 3.13.5, MediaPipe 1.2.3 và OpenCV 5.1.0.95. Mô hình đi kèm chạy trên CPU. Đã nạp mô hình, xử lý ảnh bàn tay mẫu và đọc một khung hình webcam số 0 qua DirectShow. Các phiên bản phụ thuộc được ghi trong `requirements.txt`. [Mô hình Hand Landmarker của Google](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task)

## Kết quả nghiệm thu một người

**P1 đạt nghiệm thu.** Theo kết quả người thử cung cấp ngày 26/11/2026, cả 6 lượt đều khớp câu đích, gồm cả hai lần nhập `SOS 2026`. Tỷ lệ lỗi ký tự là **0/40 (0%)**, tính cả khoảng trắng, đạt ngưỡng ≤ 10%. Tổng thời gian là **212 giây** (3 phút 32 giây), tương ứng **11,3 ký tự/phút**. Người thử xác nhận các thao tác sửa lỗi hoạt động tốt. [Dữ liệu 6 lượt theo thứ tự thực hiện](results/P1-20261126.csv)

Để tính lại kết quả:

```powershell
.\.venv\Scripts\python trials.py score results/P1-20261126.csv --one
```

## Giai đoạn 2 · Mô hình Morse cá nhân

**Mô hình cá nhân đã đạt nghiệm thu cho P1 trên webcam đã thử.** Phiên 1–2 cung cấp 120 lượt huấn luyện. Trên 60 lượt tư thế của phiên 3, mô hình phân loại đúng 1.076/1.080 khung hình trước khi áp ngưỡng tin cậy. Ngưỡng 0,60 giải mã đúng cả ba câu kiểm tra.

Ở phiên 4–5, P1 mở ứng dụng và nhập trực tiếp với 0 lần hiệu chuẩn. Cả 12 lượt đều cho văn bản cuối đúng (0 lỗi/80 ký tự sau sửa); 6 lượt có sử dụng phím xóa, tổng cộng 21 lần. Bộ hiệu chuẩn cũ phát lại trên cùng khung hình và cùng thao tác xóa có 25 lỗi/80 ký tự. Tốc độ nhập của P1 là 13,1 ký tự/phút ở phiên 4 và 17,3 ở phiên 5, tính từ dấu đầu đến lần chốt chữ cuối. Có thể dùng chế độ `learned` cho P1 với cấu hình đã thử. [Báo cáo nghiệm thu trên máy thu dữ liệu](personal-data/acceptance.json)

### Thu phiên 1–3 và huấn luyện

Chạy từ thư mục dự án bằng PowerShell. Trên môi trường đã cài phiên bản cũ, chạy lại lệnh cài phụ thuộc để bổ sung scikit-learn. Mở **mỗi phiên vào một thời điểm riêng**, cùng bàn tay và webcam. Đặt lại tay và camera như khi dùng hằng ngày.

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python experiment.py collect 1
.\.venv\Scripts\python experiment.py collect 2
.\.venv\Scripts\python experiment.py collect 3
.\.venv\Scripts\python experiment.py train
.\.venv\Scripts\python app.py --mode learned
```

- Mỗi phiên từ 1 đến 3 gồm 60 lượt với thứ tự xáo trộn, 15 lượt cho mỗi tư thế. Bấm **Bắt đầu**, đặt tay theo lời nhắc trong 1 giây rồi giữ yên thêm 1 giây. Thả ngón và bấm **Xác nhận** để lưu nhãn, hoặc **Thu lại** nếu ra hiệu sai. Lượt thiếu tay trong thời gian lấy mẫu sẽ thu lại từ đầu.
- Cuối phiên 3, nhập ba câu theo màn hình. Ứng dụng hiển thị bản giải mã thử từ mô hình chỉ học phiên 1–2. Mỗi lượt đo bắt đầu với văn bản trống. Chờ chốt chữ cuối rồi bấm **Kết thúc lượt**, kể cả khi kết quả sai. Giữ nguyên kết quả trước sửa.
- Lệnh `train` tạo `personal-data/model-v1.json` cùng `validation.json`. Báo cáo gồm ma trận nhầm lẫn (hàng là nhãn thật, cột là lớp dự đoán trên từng khung), văn bản phát lại, số lỗi ký tự và số dấu sai ở từng ngưỡng. Ngưỡng được chọn theo thứ tự ít lỗi ký tự nhất, ít dấu thừa/thay sai nhất, rồi ngưỡng thấp nhất.
- Chế độ `learned` đọc mô hình và mốc thời gian đã khóa. Tách ngón trước dấu đầu. Space và Backspace dùng để sửa. Để dùng lại chế độ hiệu chuẩn, chạy `app.py` như trước.

### Nghiệm thu ở phiên 4–5

```powershell
.\.venv\Scripts\python experiment.py collect 4
.\.venv\Scripts\python experiment.py collect 5
.\.venv\Scripts\python experiment.py compare
```

Mỗi phiên mở mới ứng dụng, thử giữ dấu, mất tay, chụm đồng thời, Space và Backspace trong phần làm quen. Trả lời câu hỏi kiểm tra thao tác theo kết quả thực tế. Nhập hai vòng `SOS 2026`, `AN NA`, `EEE TTT`. Trong sáu lượt AI, Space và Backspace xóa dấu đang nhập hoặc ký tự đã chốt gần nhất. Báo cáo ghi số lần xóa và chấm văn bản sau khi phát lại cùng các thao tác sửa cho cả hai bộ nhận diện. Sau cùng thu ba tư thế đối chứng trong cùng điều kiện. Thu trọn mỗi phiên nghiệm thu trong một buổi. Nếu cửa sổ đóng giữa chừng, cùng lệnh sẽ tiếp tục từ lượt đã xác nhận; nếu điều kiện thử đã thay đổi, giữ bộ dữ liệu cũ và thu phiên mới trong một thư mục riêng.

Lệnh `compare` dùng cùng tọa độ và thời điểm cho hai bộ nhận diện, kiểm tra văn bản AI phát lại khớp với bản ghi trực tiếp, rồi lưu `personal-data/acceptance.json`. Báo cáo có văn bản và số lỗi từng lượt, tổng lỗi trên 80 ký tự, thời gian từ lúc mở ứng dụng tới dấu đầu (kể cả dấu trong phần làm quen), và tốc độ từ dấu đầu của lượt đến khi chốt chữ cuối. Trường tốc độ để trống nếu không đo được.

**Điều kiện đạt:** cả hai phiên mở được chế độ AI với 0 lần hiệu chuẩn, thao tác điều khiển đạt, và mỗi phiên có ít nhất một lượt đúng `SOS 2026`. Tổng số lỗi AI tối đa 4/80, đồng thời không vượt số lỗi của chế độ hiệu chuẩn quá 2. Dùng kết quả này khi quyết định chuyển sang chế độ AI cho người đã huấn luyện.

**Dữ liệu và lần thử mới.** Mỗi lượt lưu JSON có mã phiên, số lượt, nhãn và dãy thời gian mili giây kèm 21 điểm. Tọa độ x/y theo pixel, z theo bề rộng ảnh; khung mất tay có giá trị `null`. Các phiên nghiệm thu ghi thêm mã SHA-256 của mô hình và kết quả trực tiếp. Ảnh webcam chỉ xử lý trong bộ nhớ. Các lần chạy mặc định lưu trong `personal-data`. Để dùng vị trí khác, thêm `--data THU_MUC` vào các lệnh `experiment.py`, và dùng `app.py --mode learned --model THU_MUC/model-v1.json`. Nếu điều chỉnh mô hình sau nghiệm thu, dùng thư mục mới, có thể sao chép phiên 1–3 và thu mới phiên 4–5. Nếu chỉ thu lại nghiệm thu, sao chép mô hình đã khóa và các phiên đã hoàn thành cần giữ sang thư mục mới.

## Buổi thử với ba người

Mỗi người hiệu chuẩn và làm quen một lượt. Tạo phiếu 18 lượt bằng lệnh đầu. Mỗi dòng là một lần nhập từ văn bản trống. Sau khi ghi kết quả, dùng Backspace để xóa văn bản trước lượt kế tiếp. Giữ nguyên ngưỡng trong cùng đợt đo.

```powershell
.\.venv\Scripts\python trials.py new ket-qua.csv
.\.venv\Scripts\python trials.py score ket-qua.csv
```

Mỗi người nhập `SOS 2026`, `AN NA`, `EEE TTT` hai lần, được xem bảng Morse. Bấm giờ từ lúc bắt đầu thao tác đến khi chốt chữ cuối. Ghi văn bản trước sửa vào `raw_text`, kể cả khoảng trắng, và thời gian giây vào `seconds`. Ghi số lần nhầm cặp ngón, đếm lặp, chốt chữ sớm vào ba cột tương ứng. Ở một lượt riêng ngoài phép đo, yêu cầu sửa một dấu bằng Backspace, ghi kết quả và nhận xét về độ thoải mái vào `notes` của người đó.

Lệnh `score` tính khoảng cách chỉnh sửa trên toàn văn bản, kể cả khoảng trắng, và chia tổng số lỗi cho tổng ký tự đích. Tốc độ là số ký tự đầu ra mỗi phút. Mục tiêu là CER gộp ≤ 10% và mỗi người nhập đúng `SOS 2026` ít nhất một lần. Kết quả webcam với ba người đang chờ thu.
