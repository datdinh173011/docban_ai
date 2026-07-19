# ICIVI — Những tính năng mới nhất

Tài liệu này tóm tắt các tính năng mới được đưa vào ICIVI gần đây nhất, mỗi
mục gồm giá trị mang lại cho người dùng/sản phẩm và ghi chú kỹ thuật ngắn gọn
cho ai cần đọc sâu hơn. Đây là tài liệu "cập nhật liên tục" (running log), bổ
sung thêm khi có tính năng mới đáng chú ý; không thay thế `00-overview.md`
(vốn mô tả toàn bộ phạm vi sản phẩm) hay `01-architecture.md` (kiến trúc kỹ
thuật đầy đủ).

---

## 1. Trang Điều khoản & Chính sách quyền riêng tư

**Giá trị:** Trước đây hệ thống chưa có nơi nào trình bày điều khoản sử dụng
và chính sách quyền riêng tư cho người dùng — một khoảng trống pháp lý/tuân
thủ với một sản phẩm công khai đang xử lý dữ liệu do người dùng tự nhập. Trang
`/privacy` lấp khoảng trống này: người dùng có thể xem điều khoản bất cứ lúc
nào từ header, bằng chính ngôn ngữ họ đang dùng trong ứng dụng, và quay lại
phiên chat đang dở mà không mất dữ liệu.

**Kỹ thuật:**
- Router thủ công dựa trên `pathname`/`history.pushState`/`popstate`
  (`fe/src/router.ts`) — không thêm thư viện router mới, phù hợp với triết lý
  "không phụ thuộc ngoài trừ khi thật cần" của `fe/`.
- Nội dung điều khoản được cấu trúc dạng dữ liệu, dịch đầy đủ sang cả 4 ngôn
  ngữ (`fe/src/privacyContent.ts`), không phải chuỗi văn bản phẳng như các
  nhãn UI khác trong `fe/src/i18n.ts`.
- Trang có bộ chọn ngôn ngữ riêng, độc lập với logic khởi tạo phiên chat của
  trang chính — chuyển ngôn ngữ trên trang điều khoản không khởi tạo lại
  session chat.

---

## 2. Giao diện Rà soát & Kiểm tra đơn được thiết kế lại, có xem trước PDF

**Giá trị:** Bảng kết quả thẩm định cũ chỉ là một khối chữ nhật tĩnh, không có
trạng thái đang xử lý và không cho biết PDF cuối cùng sẽ trông như thế nào
trước khi tải xuống — người dùng dễ tải nhầm bản chưa đúng rồi phải sửa lại và
tải lần nữa. Giao diện mới có ba trạng thái rõ ràng (chờ thẩm định / đang
thẩm định / có kết quả), một "con dấu" xác nhận kết quả trực quan theo đúng
màu và cấp độ nghiêm trọng, và quan trọng nhất là cho phép xem trước đúng file
PDF sẽ tải về ngay trong trình duyệt trước khi quyết định tải xuống.

**Kỹ thuật:**
- Ba trạng thái panel kết quả nằm trong `fe/src/ReviewForm.tsx`
  (`ResultPanel`), style thuần CSS (`fe/src/styles.css`), không dùng thư viện
  animation — hiệu ứng "con dấu" bật ra dùng `@keyframes` CSS thường.
- Bản xem trước lấy đúng file PDF thật từ backend (endpoint
  `exports/pdf` hiện có) và hiển thị qua `<iframe>` dùng trình xem PDF có sẵn
  của trình duyệt — không dựng lại bố cục PDF ở phía client, nên không bao giờ
  lệch với bản tải xuống thật. Xem trước và tải xuống dùng chung một lần gọi
  API, không gọi lặp lại.

---

## 3. Thẩm định kết hợp Rule + AI

**Giá trị:** Bộ rule tĩnh trước đây chỉ bắt được các lỗi máy móc (thiếu
trường, sai định dạng, ngày tháng vô lý) — không thể phát hiện một cái tên
nghe không hợp lý, một địa chỉ không giống địa danh thật, hay mâu thuẫn logic
đời thường giữa các trường. Lượt rà soát AI bổ sung phát hiện thêm các vấn đề
dạng này, giúp hồ sơ được kiểm tra kỹ hơn trước khi nộp mà không cần thêm rule
tĩnh cho từng trường hợp riêng lẻ.

**Kỹ thuật:**
- Module mới `be/app/form_ai_review.py`, dùng chung LLM provider đã có sẵn
  cho chatbot và tính năng auto-fill form (không thêm provider/API key mới).
- Rule tĩnh (`be/app/form_validation.py`) luôn chạy trước và là nguồn xác thực
  chính — kết quả AI chỉ được **cộng thêm**, không bao giờ xóa hay ghi đè một
  issue do rule tạo ra. Mỗi issue do AI tạo ra được gắn `rule_code` tiền tố
  `AI_` để phân biệt nguồn gốc khi cần debug/audit.
- Issue do AI tạo ra có cùng trọng số mức độ nghiêm trọng với rule — kể cả
  `blocking_error` có thể chặn export PDF — đây là quyết định sản phẩm có chủ
  đích (chấp nhận rủi ro AI báo sai để đổi lấy khả năng bắt được nhiều lỗi
  thật hơn).
- Trạng thái `unable_to_validate` (đã có sẵn trong schema nhưng trước đây
  không bao giờ được tạo ra) nay được kích hoạt: nếu AI đánh dấu một vấn đề là
  `unable_to_verify` và không có `blocking_error`/`warning` nào khác, hồ sơ
  hiển thị trạng thái "chưa rõ" thay vì mặc định "hợp lệ".
- Nếu LLM không khả dụng (thiếu cấu hình hoặc lỗi mạng/provider), hệ thống tự
  động rơi về kết quả chỉ có rule — không có lỗi, không chặn luồng thẩm định.

---

## 4. Nhập liệu bằng giọng nói (Voice input)

**Giá trị:** Trước đây người dùng chỉ có thể gõ tay mọi nội dung — bất tiện
khi mô tả một yêu cầu dài bằng lời sẽ nhanh hơn nhiều so với gõ, đặc biệt trên
điện thoại hoặc khi trả lời các câu hỏi điền đơn của chatbot. Nút micro cạnh ô
nhập liệu cho phép ghi âm rồi tự động chuyển thành văn bản, người dùng chỉ cần
xem lại và gửi như bình thường.

**Kỹ thuật:**
- Nhận diện giọng nói chạy hoàn toàn cục bộ (offline) bằng mô hình Zipformer
  tiếng Việt qua thư viện `sherpa-onnx` (`be/voice_ai/speech_to_text.py`) —
  không gửi âm thanh ra dịch vụ ngoài, đúng nguyên tắc LAN/internal-first đã
  áp dụng cho toàn hệ thống.
- Âm thanh trình duyệt ghi (WebM/Opus, Ogg/Opus hoặc MP4 tùy trình duyệt) được
  chuẩn hóa bằng `ffmpeg` thành PCM 16kHz mono trước khi đưa vào mô hình, có
  giới hạn thời lượng và timeout riêng cho bước chuẩn hóa.
- Việc kiểm tra khả dụng (`preflight()`) tách khỏi việc nạp mô hình vào bộ nhớ
  (`initialize_if_needed()`, chạy lazy ở lượt transcribe đầu tiên): một môi
  trường thiếu mô hình/thư viện/`ffmpeg` chỉ khiến nút micro tự ẩn, không làm
  lỗi hoặc chặn lúc khởi động backend.
- Việc gọi `ffmpeg` và chạy mô hình ASR thực thi trên thread pool riêng
  (`run_in_threadpool`), không chặn event loop xử lý các request khác.
- Frontend (`fe/src/VoiceInput.tsx`) dùng mô hình nhấn-để-ghi/nhấn-để-dừng,
  tự dừng và gửi sau 60 giây, cảnh báo khi gần đến giới hạn. Kết quả nhận diện
  được **thêm vào cuối** nội dung đang gõ, không thay thế và không tự gửi.
  Nút micro chỉ hiển thị khi giao diện đang ở tiếng Việt và trình duyệt hỗ trợ
  ghi âm.
- Backend giới hạn dung lượng file tải lên và phân loại lỗi rõ ràng theo mã
  trạng thái HTTP (dịch vụ chưa sẵn sàng khác với dữ liệu ghi âm không hợp
  lệ). Âm thanh chỉ tồn tại trong bộ nhớ của request; log kỹ thuật ghi số liệu
  (dung lượng, độ trễ, mã lỗi) nhưng không bao giờ ghi lại nội dung đã nhận
  diện được.
