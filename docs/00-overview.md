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

#### F. Hỗ trợ đa ngôn ngữ có khả năng mở rộng

Version 1 ưu tiên tiếng Việt.

Kiến trúc phải cho phép mở rộng sang các ngôn ngữ dân tộc thiểu số, trước mắt có thể thử nghiệm với tiếng Thái tại Việt Nam.

Việc mở rộng ngôn ngữ gồm:

- Nhận diện ngôn ngữ người dùng.
- Dịch câu hỏi sang ngôn ngữ xử lý trung gian nếu cần.
- Giữ nguyên thuật ngữ pháp lý quan trọng.
- Trả lời bằng ngôn ngữ người dùng.
- Có bảng thuật ngữ song ngữ cho tên thủ tục, giấy tờ và trường biểu mẫu.
- Cho phép quản trị nội dung theo từng ngôn ngữ.

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

Chạy các kiểm tra deterministic:

- Required field.
- Kiểu dữ liệu.
- Regex.
- Giá trị cho phép.
- Quan hệ giữa các trường.
- Điều kiện phát sinh giấy tờ.
- Quy tắc riêng của từng biểu mẫu.

#### LLM Layer

LLM được sử dụng để:

- Hiểu câu hỏi tự nhiên.
- Phân loại nhu cầu.
- Trích xuất dữ liệu từ câu người dùng.
- Diễn giải hướng dẫn.
- Giải thích lỗi bằng ngôn ngữ dễ hiểu.
- Dịch và phản hồi đa ngôn ngữ.

LLM không được tự quyết định:

- Hồ sơ hợp lệ hay không.
- Điều kiện pháp lý.
- Danh sách giấy tờ bắt buộc.
- Thời hạn.
- Cơ quan tiếp nhận.
- Nội dung của quy định.

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

## 10. Hỗ trợ tiếng Thái Việt Nam

Version 1 chưa cần hoàn thiện toàn bộ tiếng Thái, nhưng kiến trúc phải sẵn sàng cho một pilot ngôn ngữ nhỏ.

### Phương án triển khai

1. Chọn một biến thể tiếng Thái cụ thể theo khu vực pilot.
2. Xây dựng bộ thuật ngữ hành chính Việt – Thái.
3. Dịch thủ công tên thủ tục, giấy tờ và trường biểu mẫu quan trọng.
4. Sử dụng LLM để hỗ trợ dịch hội thoại.
5. Kiểm duyệt câu trả lời mẫu bởi người sử dụng ngôn ngữ bản địa.
6. Khi trích dẫn pháp lý, giữ nguyên tên và số hiệu văn bản tiếng Việt, kèm giải thích bằng tiếng Thái.

### Nguyên tắc

- Không coi “tiếng Thái” là một ngôn ngữ đồng nhất cho mọi cộng đồng.
- Phải xác định rõ biến thể ngôn ngữ của khu vực triển khai.
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
