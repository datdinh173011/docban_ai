# Chuẩn Hóa Cấu Hình RAG Trong `app/settings`

## Tóm tắt

Giữ nguyên hoàn toàn `be/app/config.py`. Thêm thư mục asset `be/app/settings/`
để chứa prompt và JSON của Procedure RAG, theo hướng gọn và an toàn từ
`civi_project_2`. Asset mặc định được đóng gói trong image; có thể override qua
volume runtime và chỉ nạp khi backend khởi động.

## Thay đổi chính

- Không đổi tên, di chuyển hoặc sửa `be/app/config.py`.
- Thêm `be/app/settings/` với prompt grounding, prompt hội thoại, taxonomy
  procedure selection và schema form guidance.
- Thêm loader tập trung để chọn bundled settings hoặc `PROCEDURE_SETTINGS_DIR`,
  validate toàn bộ bundle khi startup và fail-fast nếu không hợp lệ.
- Đưa cấu hình taxonomy vào `ProcedurePipeline`, giữ exact match, session,
  locality gate và cấm retrieval chéo thủ tục/địa bàn.
- Đưa system prompt trong `llm.py` ra asset, vẫn ghép evidence/citation theo
  logic grounding hiện có.
- Chuẩn hóa form candidate theo filename và checksum; chỉ hướng dẫn/tải mẫu khi
  mapping thủ tục-mẫu có trạng thái `reviewed`.
- Không chuyển Chroma, Streamlit, secret, fallback retrieval, dynamic auto-fill
  hoặc hard-code form replacement từ reference.

## Kiểm thử

- Test bundled settings, runtime override, JSON/schema lỗi và taxonomy field
  không hợp lệ.
- Test pipeline taxonomy, chọn bằng số/text, auto-skip, tối đa bảy lựa chọn,
  locality gate và session state.
- Test LLM đọc prompt asset mà không thay đổi quy tắc evidence/citation.
- Test form draft bị chặn và form mapping reviewed mới được hướng dẫn.
- Test backend khởi động bằng bundled settings và mounted settings; thay đổi
  runtime settings chỉ áp dụng sau restart.

## Giả định

- `be/app/config.py` tiếp tục chứa `Settings` của ứng dụng.
- `be/app/settings/` là bundle prompt/JSON production mặc định.
- Snapshot trong `be/data/dichvucong_xaydung` là nguồn tri thức duy nhất.
