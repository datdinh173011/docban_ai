import os
import json

class ClassificationAgent:
    def __init__(self):
        # Load the exported JSON data files
        with open('src/data/phan_loai_tthc.json', 'r', encoding='utf-8') as f:
            self.phan_loai = json.load(f)
        with open('src/data/cay_hoi_ai.json', 'r', encoding='utf-8') as f:
            self.cay_hoi = json.load(f)
        with open('src/data/cau_hoi_theo_de_muc.json', 'r', encoding='utf-8') as f:
            self.cau_hoi_de_muc = json.load(f)

    def run(self, state):
        messages = state.get("messages", [])
        last_message = messages[-1].content if messages else ""
        
        step = state.get("classification_step", 1)
        filters = state.get("filters", {})
        candidates = state.get("candidates", [])
        
        # Initialize candidates if first step
        if step == 1 or not candidates:
            candidates = self.phan_loai
            filters = {}
            
        # If user typed something and it's not the initial trigger, we process their response
        if len(messages) > 1 and last_message and not last_message.startswith("/"):
            # Process user response for the previous step
            prev_step = step - 1
            filters, candidates = self._process_user_response(prev_step, last_message, filters, candidates)
            
        # Check if we have narrowed down to 1 candidate
        if len(candidates) == 1:
            selected = candidates[0]
            # Format procedure details
            proc_details = {
                "id": selected.get("Id") or selected.get("Mã số"),
                "code": selected.get("Mã số"),
                "name": selected.get("Tên"),
                "co_quan_thuc_hien": selected.get("Cơ quan thực hiện", "Không rõ cơ quan thực hiện"),
                "cap_thuc_hien": selected.get("Cấp thực hiện")
            }
            return {
                "classification_step": 8,
                "selected_procedure": proc_details,
                "candidates": candidates,
                "filters": filters,
                "response": f"Đã xác định thủ tục: **{proc_details['name']}** (Mã số: {proc_details['code']})\nCơ quan thực hiện: {proc_details['co_quan_thuc_hien']}"
            }
            
        if len(candidates) == 0:
            # Fallback if filters are too strict - reset
            candidates = self.phan_loai
            filters = {}
            step = 1
            
        # Determine question and options for current step
        question, options = self._get_question_and_options(step, filters, candidates)
        
        # If there is only 1 option available, automatically apply it and proceed to next step
        while len(options) == 1 and step <= 7:
            opt = options[0]
            filters, candidates = self._apply_filter(step, opt, filters, candidates)
            step += 1
            if len(candidates) <= 1:
                break
            question, options = self._get_question_and_options(step, filters, candidates)

        # If candidates are 1 now, return selected
        if len(candidates) == 1:
            selected = candidates[0]
            proc_details = {
                "id": selected.get("Id") or selected.get("Mã số"),
                "code": selected.get("Mã số"),
                "name": selected.get("Tên"),
                "co_quan_thuc_hien": selected.get("Cơ quan thực hiện", "Không rõ cơ quan thực hiện"),
                "cap_thuc_hien": selected.get("Cấp thực hiện")
            }
            return {
                "classification_step": 8,
                "selected_procedure": proc_details,
                "candidates": candidates,
                "filters": filters,
                "response": f"Đã xác định thủ tục: **{proc_details['name']}** (Mã số: {proc_details['code']})\nCơ quan thực hiện: {proc_details['co_quan_thuc_hien']}"
            }
            
        # Format options as string
        options_text = ""
        for idx, opt in enumerate(options[:7], 1):
            options_text += f"\n{idx}. {opt}"
        if len(options) > 7:
            options_text += f"\n8. Khác/Chưa rõ"
            
        return {
            "classification_step": step + 1,
            "filters": filters,
            "candidates": candidates,
            "response": f"{question}\n{options_text}"
        }

    def _get_question_and_options(self, step, filters, candidates):
        # Step definitions:
        # 1: Nhóm nhu cầu (Nhóm đề mục)
        # 2: Lĩnh vực chuẩn hóa
        # 3: Loại yêu cầu
        # 4: Tình huống/đối tượng hồ sơ
        # 5: Địa bàn / Địa phương
        # 6: Đối tượng người dùng
        # 7: Xác nhận
        
        if step == 1:
            question = "Bạn đang cần giải quyết vấn đề thuộc nhóm nhu cầu nào?"
            options = sorted(list(set(str(c.get("Nhóm đề mục")) for c in candidates if c.get("Nhóm đề mục"))))
            return question, options
        elif step == 2:
            question = "Nhu cầu của bạn thuộc lĩnh vực cụ thể nào?"
            options = sorted(list(set(str(c.get("Lĩnh vực chuẩn hóa")) for c in candidates if c.get("Lĩnh vực chuẩn hóa"))))
            return question, options
        elif step == 3:
            question = "Bạn muốn thực hiện loại yêu cầu nào?"
            options = sorted(list(set(str(c.get("Loại yêu cầu")) for c in candidates if c.get("Loại yêu cầu"))))
            return question, options
        elif step == 4:
            question = "Tình huống cụ thể của bạn liên quan đến đối tượng/tình huống nào?"
            options = sorted(list(set(str(c.get("Tình huống/đối tượng hồ sơ")) for c in candidates if c.get("Tình huống/đối tượng hồ sơ"))))
            return question, options
        elif step == 5:
            question = "Bạn thực hiện thủ tục tại địa bàn/địa phương nào?"
            options = sorted(list(set(str(c.get("Địa phương")) for c in candidates if c.get("Địa phương"))))
            return question, options
        elif step == 6:
            question = "Đối tượng nộp hồ sơ là ai?"
            options = sorted(list(set(str(c.get("Đối tượng người dùng")) for c in candidates if c.get("Đối tượng người dùng"))))
            return question, options
        else:
            question = "Vui lòng xác nhận thủ tục nào phù hợp nhất với bạn:"
            options = [f"{c.get('Tên')} (Mã số: {c.get('Mã số')}) - {c.get('Cơ quan thực hiện')}" for c in candidates[:5]]
            return question, options

    def _apply_filter(self, step, value, filters, candidates):
        col_map = {
            1: "Nhóm đề mục",
            2: "Lĩnh vực chuẩn hóa",
            3: "Loại yêu cầu",
            4: "Tình huống/đối tượng hồ sơ",
            5: "Địa phương",
            6: "Đối tượng người dùng"
        }
        col = col_map.get(step)
        if col:
            filters[col] = value
            candidates = [c for c in candidates if str(c.get(col)) == str(value)]
        return filters, candidates

    def _process_user_response(self, prev_step, user_text, filters, candidates):
        question, options = self._get_question_and_options(prev_step, filters, candidates)
        
        # Try numeric matching first (e.g. user typed "1" or "2")
        cleaned_text = user_text.strip()
        if cleaned_text.isdigit():
            idx = int(cleaned_text) - 1
            if 0 <= idx < len(options):
                return self._apply_filter(prev_step, options[idx], filters, candidates)
                
        # Try text matching (substring in either direction)
        for opt in options:
            if opt.lower() in cleaned_text.lower() or cleaned_text.lower() in opt.lower():
                return self._apply_filter(prev_step, opt, filters, candidates)
                
        # Default fallback: do not filter, keep candidates
        return filters, candidates

