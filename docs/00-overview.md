# ICIVI — Overview Version 1

## 1. Tổng quan

ICIVI là chatbot AI hỗ trợ người dân tiếp cận và thực hiện thủ tục hành chính công bằng ngôn ngữ tự nhiên.

Trong Version 1, ICIVI không thay thế cổng dịch vụ công và không trực tiếp tiếp nhận hay nộp hồ sơ. Hệ thống đóng vai trò là lớp hỗ trợ trước khi nộp, giúp người dân:

- Hỏi đáp quy định và thủ tục hành chính.
- Xác định đúng thủ tục cần thực hiện.
- Biết cần chuẩn bị giấy tờ, biểu mẫu và thông tin gì.
- Được hướng dẫn điền từng mục trong đơn.
- Kiểm tra sơ bộ nội dung đã điền.
- Giải đáp thắc mắc trong suốt quá trình chuẩn bị hồ sơ.

Mục tiêu của Version 1 là xây dựng một chatbot công khai, dễ sử dụng, hoạt động theo từng phiên trò chuyện và có thể mở rộng cho nhiều loại thủ tục, biểu mẫu và ngôn ngữ.

---

## 2. Vấn đề cần giải quyết

Khi thực hiện thủ tục hành chính, người dân thường gặp các khó khăn sau:

1. Không biết thủ tục nào phù hợp với nhu cầu của mình.
2. Không biết cần chuẩn bị những giấy tờ hoặc biểu mẫu nào.
3. Không hiểu cách điền các trường trong đơn.
4. Không phát hiện được thông tin còn thiếu, sai định dạng hoặc mâu thuẫn trước khi nộp.
5. Khó hiểu ngôn ngữ hành chính và quy định pháp luật.
6. Người sử dụng ngôn ngữ dân tộc thiểu số gặp thêm rào cản về ngôn ngữ.

ICIVI giúp giảm số lần người dân phải tìm kiếm thông tin ở nhiều nguồn hoặc đi lại để hỏi trực tiếp cán bộ.

---

## 3. Phạm vi Version 1

### 3.1 Trong phạm vi

Version 1 hỗ trợ các chức năng sau:

#### A. Chatbot công khai theo phiên

- Người dùng truy cập chatbot qua một URL công khai.
- Không yêu cầu đăng nhập hoặc tạo tài khoản.
- Mỗi lần truy cập tạo một `chat session`.
- Lịch sử và trạng thái hội thoại chỉ được duy trì trong phạm vi phiên.
- Phiên hết hạn sau 30 phút không hoạt động và được xóa ngay khi người dùng kết thúc phiên.
- Người dùng có thể bắt đầu phiên mới bất kỳ lúc nào.

#### B. Xác định nhu cầu và thủ tục

Người dùng mô tả nhu cầu bằng ngôn ngữ tự nhiên, ví dụ:

- “Tôi muốn đăng ký khai sinh cho con.”
- “Tôi muốn xây thêm một tầng cho nhà.”
- “Tôi cần xin giấy phép xây dựng.”
- “Tôi chưa biết mục người đề nghị trong đơn phải ghi thế nào.”

Chatbot xác định nhóm thủ tục hoặc biểu mẫu phù hợp. Nếu thông tin chưa đủ, chatbot hỏi thêm một số câu ngắn để làm rõ.

Khi câu trả lời phụ thuộc nơi thực hiện, chatbot hỏi tỉnh hoặc thành phố của người dùng. Hệ thống chỉ hỏi quận, huyện hoặc xã, phường khi thủ tục hoặc dữ liệu đã publish yêu cầu. Không hỏi địa chỉ đầy đủ mặc định.

#### C. Hỏi đáp quy định và thủ tục

Chatbot trả lời các câu hỏi như:

- Thủ tục này dành cho ai?
- Hồ sơ cần những giấy tờ gì?
- Nộp ở đâu?
- Thời gian xử lý bao lâu?
- Có phải nộp lệ phí không?
- Trường hợp nào cần bổ sung giấy tờ?
- Căn cứ pháp lý là văn bản nào?

Mỗi câu trả lời liên quan đến quy định phải đi kèm nguồn tham chiếu.

#### D. Hướng dẫn điền đơn

Chatbot giải thích từng trường trong biểu mẫu:

- Trường này có ý nghĩa gì?
- Ai phải điền?
- Điền theo giấy tờ nào?
- Định dạng dữ liệu là gì?
- Có bắt buộc hay không?
- Ví dụ điền đúng.

#### E. Kiểm tra sơ bộ nội dung đã điền

Người dùng có thể nhập hoặc dán nội dung đã điền để chatbot kiểm tra sơ bộ:

- Thiếu trường bắt buộc.
- Sai định dạng.
- Giá trị không hợp lệ.
- Mâu thuẫn giữa các trường.
- Thông tin chưa rõ hoặc có nguy cơ bị yêu cầu bổ sung.
- Thiếu giấy tờ tương ứng với nội dung khai báo.

Kết quả kiểm tra được chia thành:

- `blocking_error`: cần sửa trước khi nộp.
- `warning`: nên kiểm tra lại.
- `suggestion`: gợi ý cải thiện.
- `unable_to_verify`: hệ thống chưa có đủ căn cứ để xác minh.

LLM chỉ giải thích kết quả. Việc xác định lỗi phải dựa trên schema và rule được cấu hình cho từng biểu mẫu.

#### F. Tạo PDF từ biểu mẫu đã xác nhận

Version 1 cho phép người dùng tạo PDF đã điền cho ba mẫu đã được chuẩn hóa và
publish:

1. Đơn đề nghị cấp giấy phép xây dựng.
2. Tờ khai đăng ký khai sinh.
3. Tờ khai đăng ký thường trú (mẫu CT01).

Thông tin chatbot trích xuất chỉ dùng để prefill. Người dùng phải xem, sửa nếu
cần và xác nhận dữ liệu trong form động. Hệ thống chỉ cho tạo PDF khi kết quả
validation không còn `blocking_error`; `warning` và `suggestion` vẫn được hiển
thị nhưng không chặn export. Trước khi tải xuống, người dùng có thể xem trước
đúng file PDF sẽ được tạo ngay trong trình duyệt (bản xem trước dùng chung một
lần gọi export với bản tải xuống thật, không render lại ở client).

PDF là bản hỗ trợ chuẩn bị hồ sơ, không có chữ ký số và không thay thế biểu mẫu
hoặc căn cứ pháp lý chính thức. File được stream để tải xuống, không lưu trên
disk, database, backup hoặc application log.

Biểu mẫu trích lục hộ tịch chưa hỗ trợ export cho đến khi có template PDF nền
và field mapping được review, publish.

#### G. Hỗ trợ đa ngôn ngữ

Version 1 đã triển khai bốn ngôn ngữ giao diện: tiếng Việt (ngôn ngữ gốc),
tiếng Anh, tiếng Hmong (Hmong Daw) và tiếng Khmer — áp dụng xuyên suốt giao
diện chat, hướng dẫn điền đơn và trang điều khoản/quyền riêng tư.

Kiến trúc vẫn giữ nguyên các nguyên tắc mở rộng ngôn ngữ ban đầu, để có thể bổ
sung thêm ngôn ngữ dân tộc thiểu số khác trong tương lai:

- Nhận diện ngôn ngữ người dùng.
- Dịch câu hỏi sang ngôn ngữ xử lý trung gian nếu cần.
- Giữ nguyên thuật ngữ pháp lý quan trọng.
- Trả lời bằng ngôn ngữ người dùng.
- Có bảng thuật ngữ song ngữ cho tên thủ tục, giấy tờ và trường biểu mẫu.
- Cho phép quản trị nội dung theo từng ngôn ngữ.

#### H. Điều khoản sử dụng & Chính sách quyền riêng tư

Trang `/privacy` trình bày điều khoản sử dụng và chính sách quyền riêng tư của
hệ thống, truy cập được từ header của giao diện chat và có đường dẫn quay lại.
Nội dung được dịch đầy đủ sang tất cả các ngôn ngữ hệ thống hỗ trợ (xem mục
3.1.G ở trên).

#### I. Nhập liệu bằng giọng nói (Voice input)

Người dùng có thể nhấn nút micro để bắt đầu ghi âm câu hỏi hoặc nội dung cần
điền thay vì gõ tay, rồi nhấn "Dừng ghi âm" khi nói xong (bản ghi tự dừng sau
60 giây nếu người dùng quên dừng, có cảnh báo khi gần đến giới hạn). Hệ thống
chuyển đoạn ghi âm thành văn bản và **thêm vào cuối** nội dung đang có trong ô
nhập liệu để người dùng xem lại, sửa nếu cần rồi mới gửi — hệ thống không tự
động gửi thẳng bản ghi âm chưa qua xác nhận.

- Mô hình tương tác là ghi-rồi-gửi (nhấn để bắt đầu, nhấn để dừng), không phải
  nhận diện liên tục theo thời gian thực.
- Nhận diện giọng nói chạy cục bộ (offline) bằng mô hình chạy trên máy chủ,
  không gửi âm thanh ra dịch vụ ngoài — phù hợp nguyên tắc LAN/internal-first
  của hệ thống.
- Chỉ hỗ trợ tiếng Việt: nút micro chỉ hiển thị khi giao diện đang ở tiếng
  Việt, không hiển thị khi người dùng chọn tiếng Anh, Hmong Daw hoặc Khmer.
- Nút micro tự ẩn nếu trình duyệt không hỗ trợ ghi âm hoặc máy chủ báo dịch vụ
  nhận diện giọng nói chưa sẵn sàng, không chặn các luồng nhập liệu khác của
  chatbot.
- Âm thanh người dùng chỉ xử lý trong bộ nhớ của request, không lưu lại dưới
  bất kỳ hình thức nào (xem mục 6.2 của `01-architecture.md`).
- Đây là nhập liệu bằng giọng nói (speech-to-text) cho khung chat hiện có;
  chatbot không đọc câu trả lời bằng giọng nói (xem mục 3.2).

---

### 3.2 Ngoài phạm vi Version 1

Version 1 chưa hỗ trợ:

- Đăng nhập, đăng ký tài khoản hoặc quản lý hồ sơ người dùng.
- Xác thực VNeID hoặc kết nối cơ sở dữ liệu dân cư.
- Tự động lấy dữ liệu cá nhân.
- Lưu hồ sơ lâu dài giữa nhiều phiên chat.
- Nộp hồ sơ trực tiếp lên cổng dịch vụ công.
- Thanh toán lệ phí.
- Ký số.
- Theo dõi trạng thái xử lý hồ sơ.
- Tự động quyết định thay cơ quan nhà nước.
- Kiểm tra tính xác thực pháp lý của bản scan giấy tờ.
- OCR tài liệu phức tạp trong giai đoạn đầu.
- Hỗ trợ toàn bộ thủ tục hành chính ngay từ khi ra mắt.
- Export PDF cho form chưa có template PDF nền và field mapping đã publish.
- Lưu PDF đã tạo lâu dài, ký số hoặc nộp trực tiếp PDF lên cổng dịch vụ công.
- Trả lời bằng giọng nói (text-to-speech) cho câu trả lời của chatbot.
- Nhận diện giọng nói theo thời gian thực (streaming) cho nhập liệu bằng
  giọng nói (xem mục 3.1.I).
- Nhận diện giọng nói cho ngôn ngữ khác ngoài tiếng Việt — nút micro chỉ xuất
  hiện khi giao diện đang ở tiếng Việt, không chỉ là hạn chế của mô hình.

---

## 4. Nhóm biểu mẫu dữ liệu ban đầu

Version 1 triển khai ba biểu mẫu đại diện cho các nhóm thủ tục khác nhau.

### Biểu mẫu ưu tiên

1. Đơn đề nghị cấp giấy phép xây dựng.
2. Tờ khai đăng ký khai sinh.
3. Biểu mẫu trích lục hộ tịch có số trường ít hơn để làm use case onboarding.

### Mỗi biểu mẫu cần chuẩn bị

- Mã thủ tục.
- Tên thủ tục.
- Mô tả và đối tượng thực hiện.
- Cơ quan tiếp nhận.
- Cách thức thực hiện.
- Thành phần hồ sơ.
- Trình tự thực hiện.
- Thời hạn giải quyết.
- Lệ phí.
- Căn cứ pháp lý.
- File biểu mẫu gốc.
- Danh sách các trường trong biểu mẫu.
- Kiểu dữ liệu của từng trường.
- Trường bắt buộc và tùy chọn.
- Hướng dẫn điền.
- Ví dụ điền.
- Validation rule.
- Cross-field rule.
- Danh sách lỗi phổ biến.
- Phiên bản và thời gian hiệu lực.
- Nguồn dữ liệu chính thức.
- Phạm vi địa bàn áp dụng.

---

## 5. Mô hình tương tác

ICIVI sử dụng mô hình tương tác gồm bốn năng lực chính:

### 5.1 Hỏi đáp thủ tục

Người dân hỏi câu hỏi tự do. Chatbot tìm thông tin trong dữ liệu thủ tục và văn bản pháp lý để trả lời có trích dẫn.

### 5.2 Tư vấn chọn thủ tục

Chatbot phân tích nhu cầu, đưa ra thủ tục phù hợp hoặc hỏi thêm để phân biệt giữa các thủ tục gần giống nhau.

### 5.3 Tư vấn điền đơn

Chatbot hướng dẫn theo từng trường, từng nhóm thông tin hoặc từng bước của biểu mẫu.

### 5.4 Kiểm tra trước khi nộp

Chatbot tiếp nhận dữ liệu đã điền, gọi Validation Engine và giải thích những nội dung cần sửa.

---

## 6. Luồng người dùng tối thiểu

### Luồng 1 — Hỏi thủ tục

1. Người dùng nhập nhu cầu.
2. Chatbot xác định thủ tục.
3. Chatbot hỏi thêm nếu cần.
4. Chatbot trả danh sách hồ sơ, các bước thực hiện, nơi nộp và nguồn tham chiếu.

### Luồng 2 — Hướng dẫn điền đơn

1. Người dùng chọn một biểu mẫu.
2. Chatbot hiển thị danh sách nhóm thông tin cần điền.
3. Người dùng hỏi về một trường cụ thể.
4. Chatbot giải thích và đưa ví dụ.

### Luồng 3 — Kiểm tra nội dung đơn

1. Người dùng chọn biểu mẫu.
2. Người dùng nhập hoặc dán dữ liệu đã điền.
3. Hệ thống chuẩn hóa dữ liệu.
4. Validation Engine chạy schema validation và business rules.
5. Chatbot giải thích lỗi và gợi ý cách sửa.
6. Người dùng sửa và kiểm tra lại.

### Luồng 4 — Tạo PDF

1. Chatbot prefill dữ liệu đã trích xuất vào form động.
2. Người dùng xem, sửa và xác nhận dữ liệu.
3. Validation Engine chạy lại và trả `validation_id` cùng `input_hash`.
4. Nếu không có `blocking_error`, người dùng chọn tạo PDF.
5. Hệ thống render PDF từ template đã publish và stream file để tải xuống.

---

## 7. Kiến trúc logic Version 1

```text
Public Chat UI
      |
      v
Session API
      |
      v
Conversation Orchestrator
      |
      +--> Intent & Procedure Selection
      |
      +--> Guided Intake
      |
      +--> Legal and Procedure RAG
      |
      +--> Form Guidance Service
      |
      +--> Application Validation Engine
      |
      +--> Form PDF Export Service
      |
      v
Response Generator
```

### Các thành phần chính

#### Public Chat UI

- Giao diện web công khai.
- Không yêu cầu đăng nhập.
- Hỗ trợ desktop và mobile.
- Có thể chọn ngôn ngữ.
- Có nút bắt đầu phiên mới.

#### Session API

- Tạo `session_id` ngẫu nhiên.
- Lưu state ngắn hạn.
- Có thời gian hết hạn.
- Không yêu cầu danh tính người dùng.

#### Conversation Orchestrator

Quản lý luồng hội thoại:

- Nhận diện ý định.
- Chọn thủ tục.
- Hỏi thông tin còn thiếu.
- Chuyển sang tư vấn điền đơn hoặc kiểm tra đơn.
- Kiểm soát fallback khi thiếu dữ liệu.

#### Procedure Knowledge Base

Lưu dữ liệu có cấu trúc:

- Thủ tục.
- Biểu mẫu.
- Trường dữ liệu.
- Hồ sơ cần chuẩn bị.
- Trình tự.
- Cơ quan tiếp nhận.
- Phiên bản hiệu lực.

#### Legal RAG

Lưu và truy xuất:

- Luật.
- Nghị định.
- Thông tư.
- Quyết định.
- Hướng dẫn thực hiện.
- FAQ đã được kiểm duyệt.

#### Application Validation Engine

Chạy các kiểm tra deterministic, luôn thực thi trước và không bao giờ bị bỏ
qua hay ghi đè:

- Required field.
- Kiểu dữ liệu.
- Regex.
- Giá trị cho phép.
- Quan hệ giữa các trường.
- Điều kiện phát sinh giấy tờ.
- Quy tắc riêng của từng biểu mẫu.

Sau bước deterministic, một lượt AI thứ hai (dùng chung LLM provider với
chatbot) rà soát thêm các vấn đề mà rule tĩnh không diễn đạt được (tên/địa chỉ
có vẻ không hợp lý, mâu thuẫn logic giữa các trường). Kết quả AI được cộng
thêm vào danh sách issue hiện có — không thay thế hay xóa issue do rule tạo ra
— và có cùng trọng số mức độ nghiêm trọng (`blocking_error` từ AI vẫn chặn
export PDF như từ rule), nhưng mỗi issue do AI tạo ra được gắn `rule_code` tiền
tố `AI_` để phân biệt nguồn gốc. Nếu LLM không khả dụng, hệ thống tự động rơi
về kết quả chỉ có rule, không lỗi, không chặn luồng thẩm định.

#### Form PDF Export Service

- Chỉ dùng template PDF nền và field mapping đã publish.
- Kiểm tra session, `validation_id`, `input_hash` và `blocking_error`.
- Render dữ liệu đã xác nhận lên PDF và flatten trước khi stream download.
- Không gọi LLM hoặc lưu PDF chứa thông tin cá nhân.

#### LLM Layer

LLM được sử dụng để:

- Hiểu câu hỏi tự nhiên.
- Phân loại nhu cầu.
- Trích xuất dữ liệu từ câu người dùng.
- Diễn giải hướng dẫn.
- Giải thích lỗi bằng ngôn ngữ dễ hiểu.
- Dịch và phản hồi đa ngôn ngữ.
- Rà soát bổ sung dữ liệu biểu mẫu sau bước kiểm tra deterministic (xem mục
  Application Validation Engine ở trên) — đây là lời gọi LLM duy nhất được
  phép đóng góp trực tiếp vào kết quả `blocking_error`/`warning`/`suggestion`/
  `unable_to_verify` của một biểu mẫu.

Ngoài lượt rà soát bổ sung nói trên, LLM (ở vai trò hội thoại/giải thích)
không được tự quyết định:

- Điều kiện pháp lý.
- Danh sách giấy tờ bắt buộc.
- Thời hạn.
- Cơ quan tiếp nhận.
- Nội dung của quy định.

Những nội dung này luôn lấy từ dữ liệu đã cấu hình hoặc RAG có trích dẫn, LLM
chỉ diễn giải chứ không tự bịa ra.

---

## 8. Mô hình dữ liệu tối thiểu

```text
procedure
procedure_version
procedure_step
procedure_required_document
procedure_legal_source
form_template
form_field
form_field_translation
form_export_template
validation_rule
cross_field_rule
common_error
faq
chat_session
chat_message
```

`chat_session` và `chat_message` là runtime state trong Redis, không phải bảng PostgreSQL lưu lịch sử hội thoại lâu dài.

### Ví dụ `form_field`

```json
{
  "field_code": "applicant_full_name",
  "label": "Họ và tên người đề nghị",
  "data_type": "string",
  "required": true,
  "max_length": 100,
  "instruction": "Ghi đầy đủ họ và tên theo giấy tờ tùy thân.",
  "example": "Nguyễn Văn An"
}
```

### Ví dụ `validation_rule`

```json
{
  "field_code": "citizen_id",
  "rule_type": "regex",
  "expression": "^[0-9]{12}$",
  "severity": "blocking_error",
  "message": "Số định danh cá nhân phải có đúng 12 chữ số."
}
```

---

## 9. Dữ liệu và nguồn dữ liệu

Nguồn dữ liệu ưu tiên:

- Cổng Dịch vụ công Quốc gia.
- Cổng dịch vụ công của bộ, ngành và địa phương.
- Cơ sở dữ liệu quốc gia về thủ tục hành chính.
- Danh mục và file biểu mẫu chính thức.
- Văn bản pháp luật từ nguồn chính thức.
- Hướng dẫn của cơ quan tiếp nhận.

Mỗi bản ghi cần có:

- `source_url`
- `source_name`
- `source_updated_at`
- `effective_from`
- `effective_to`
- `version`
- `review_status`
- `jurisdiction_scope`
- `administrative_area_code` nếu phạm vi không phải toàn quốc

Dữ liệu chỉ được đưa vào sử dụng sau khi đã được chuẩn hóa và kiểm tra.

Khi chưa có dữ liệu đã publish cho địa bàn người dùng chọn, chatbot chỉ trả nội dung toàn quốc có nguồn nếu có, nêu rõ giới hạn và dẫn người dùng tới cổng hoặc cơ quan tiếp nhận chính thức. Hệ thống không suy diễn từ dữ liệu của địa phương khác.

---

## 10. Hỗ trợ đa ngôn ngữ dân tộc thiểu số

Version 1 đã triển khai đầy đủ bốn ngôn ngữ giao diện: tiếng Việt, tiếng Anh,
tiếng Hmong (Hmong Daw) và tiếng Khmer — không còn ở giai đoạn pilot. Mục này
mô tả phương án đã áp dụng cho Hmong/Khmer và sẽ tiếp tục áp dụng cho các
ngôn ngữ dân tộc thiểu số khác được bổ sung sau này.

### Phương án triển khai

1. Chọn một biến thể ngôn ngữ cụ thể theo cộng đồng mục tiêu (ví dụ: Hmong Daw
   thay vì gộp chung các phương ngữ Hmong).
2. Xây dựng bộ thuật ngữ hành chính song ngữ Việt – ngôn ngữ đích.
3. Dịch thủ công tên thủ tục, giấy tờ, trường biểu mẫu và nội dung điều
   khoản/quyền riêng tư.
4. Sử dụng LLM để hỗ trợ dịch hội thoại thời gian thực trong phiên chat.
5. Kiểm duyệt câu trả lời mẫu bởi người sử dụng ngôn ngữ bản địa trước khi
   phát hành rộng.
6. Khi trích dẫn pháp lý, giữ nguyên tên và số hiệu văn bản tiếng Việt, kèm
   giải thích bằng ngôn ngữ đích.

### Nguyên tắc

- Không coi một ngôn ngữ dân tộc thiểu số là đồng nhất cho mọi cộng đồng nói
  ngôn ngữ đó.
- Phải xác định rõ biến thể ngôn ngữ cụ thể được hỗ trợ.
- Nội dung pháp lý gốc vẫn là tiếng Việt.
- Bản dịch dùng để hỗ trợ hiểu, không thay thế văn bản pháp lý gốc.

---

## 11. Yêu cầu phi chức năng

- Mọi câu trả lời pháp lý phải có nguồn.
- Không lưu thông tin nhạy cảm lâu hơn thời gian sống của session.
- Không ghi dữ liệu người dùng đầy đủ vào application log.
- Session tự động hết hạn sau 30 phút không hoạt động.
- Có cơ chế xóa session.
- Có fallback khi LLM hoặc RAG không trả kết quả.
- Có cảnh báo rõ khi hệ thống chưa đủ căn cứ.
- Validation chạy p95 dưới 1 giây cho một biểu mẫu chuẩn.
- Với LLM API bên ngoài, streaming có time-to-first-token p95 dưới 5 giây và phản hồi thông thường hoàn tất p95 dưới 20 giây, không tính thời gian người dùng nhập dữ liệu.
- Với local model, các ngưỡng tương ứng phải được đo và chấp thuận theo cấu hình phần cứng trước khi release.

---
