# Báo cáo Day27 HITL PR Review

Ứng dụng đã đăng review lên PR #1 và PR #2 bằng tài khoản `may31st`. Các phiên chạy sử dụng GitHub và LLM thật, giữ nguyên confidence do mô hình trả về. Ảnh được chụp trên trình duyệt, còn audit được xuất từ SQLite. Không dùng API giả lập trong các lần thu thập bằng chứng này.

## 1. Kết quả Exercise 1 trên CLI

| PR | Confidence trong log đã lưu | Nhánh |
|---|---|---|
| PR #1 | 70% | human_approval |
| PR #2 | 60% | human_approval |

Có thể xem log của [PR #1](exercise1-pr1.log) và [PR #2](exercise1-pr2.log) để đối chiếu. Trong lần chạy này, cả hai PR đều vào nhánh human_approval, nên chưa đạt checkpoint "hai PR vào hai nhánh khác nhau" của Exercise 1. Confidence có thể thay đổi giữa các lần gọi LLM; kết quả và ngưỡng được giữ nguyên khi ghi nhận bằng chứng.

## 2. PR #2: escalation và khôi phục phiên bằng SQLite

Thread: `b49000a4-79b8-4465-826b-fa9d0ce83411`.

Sau khi khởi động lại Streamlit, ứng dụng khôi phục phiên đã lưu và hiển thị các câu hỏi đang chờ. Graph tiếp tục trên cùng thread, không tải lại PR hay phân tích lại từ đầu.

1. [Màn hình escalation](01-pr2-escalation-before.png) hiển thị confidence 55% cùng bốn câu hỏi về MD5, SQL injection và xử lý lỗi mạng.
2. [Các câu trả lời](02-pr2-answers.png) nêu rõ phần ngữ cảnh chưa xác minh. Câu trả lời không giả định kế hoạch triển khai hoặc coi các rủi ro đã được sửa.
3. Khi bấm Submit answers, graph tiếp tục, ghi nhận reviewer `may31st` và gọi LLM tổng hợp review. Confidence sau bước này là 50%.
4. Lần đăng review đầu tiên nhận HTTP 403 từ GitHub. Một lần thử lại để lấy thông báo lỗi API cụ thể cũng thất bại; audit ghi nhận cả hai lần.

[Review sau khi tổng hợp](pr2-refined-review.md) gồm nội dung nhận xét và phần hỏi đáp. [Log replay](audit-pr2-replay.log) ghi lại luồng xử lý:

```text
fetch_pr → analyze → route → escalate (pending)
→ escalate (resume) → synthesize → commit (commit_failed)
```

Dòng pending xuất hiện lại vì LangGraph chạy lại node từ đầu khi resume. Sau khi thay token, node commit được chạy lại từ checkpoint sau synthesize. Phiên giữ nguyên review và câu trả lời đã có, không gọi lại LLM hay đăng lại những comment đã thành công. Log replay giữ cả các lần thất bại và lần đăng thành công cuối cùng.

GitHub trả HTTP 201 lúc `2026-10-15T16:43:43Z` (23:43:43 giờ Việt Nam). Graph kết thúc với `final_action = committed_after_escalation`, confidence 50%.

- [Comment của may31st trên PR #2](https://github.com/VinUni-AI20k/PR-Demo/pull/2#issuecomment-6197316976).
- [Kết quả thành công trên Streamlit](03-pr2-success.png), [audit trên giao diện](04-pr2-audit-success.png) và [comment trên GitHub](05-github-pr2-comment.png).
- [Phản hồi tạo comment](github-post-response.json) và [kết quả đọc lại qua API](github-pr2-verification.json). Tác giả là `may31st`, nội dung khớp review đã lưu.

## 3. PR #1: nhánh tự động trong Exercise 2

Khi chạy nguyên bản `exercises/exercise_2_hitl.py` với GitHub và LLM thật, mô hình trả confidence 85%. Graph chọn nhánh auto_approve, đăng comment và kết thúc với `auto_approved`.

Input `approve` đã được chuẩn bị nhưng không được sử dụng vì phiên không đi qua interrupt. Vì vậy, lần chạy này chỉ xác nhận nhánh tự động; bằng chứng bấm Approve được ghi riêng ở phần 4.

- [Comment của may31st trên PR #1](https://github.com/VinUni-AI20k/PR-Demo/pull/1#issuecomment-6197385176).
- [Log Exercise 2](exercise2-pr1-live.log) và [ảnh comment trên GitHub](06-github-pr1-comment.png).
- [Kết quả xác minh qua API](github-pr1-verification.json) và [nội dung comment đã đăng](github-pr1-comment.md).

Thread của phiên là `2fc71c04-b45e-4c00-be66-5d1fa2b81532`. Exercise 2 dùng MemorySaver nên thread này không nằm trong audit SQLite của Exercise 4.

## 4. PR #1: chờ duyệt và bấm Approve

Thread: `b98141fa-ed3d-481a-a5e0-ea9036ad5716`.

Phiên này dùng analyzer của Exercise 1 cùng các node HITL và audit của Exercise 4, được ghép bằng [script tái hiện](run_human_approval_demo.py). LLM trả confidence 70%, với hai ngưỡng vẫn giữ ở 0.58 và 0.73. Đây là cấu hình tích hợp để kiểm chứng luồng chờ duyệt. Analyzer mặc định của Exercise 4 trong các lần chạy trước trả 55%, và các phiên đó đã dừng trước route.

Sau khi mở checkpoint trên Streamlit, thẻ chờ duyệt hiển thị review đề xuất. Khi điền feedback và bấm Approve, graph tiếp tục, đăng comment rồi kết thúc với `final_action=committed`, `human_choice=approve`.

- [Trước khi bấm Approve](07-pr1-human-approval-before.png), [kết quả đăng thành công](08-pr1-human-approval-success.png) và [audit trên giao diện](09-pr1-human-approval-audit.png).
- [Comment trên PR #1](https://github.com/VinUni-AI20k/PR-Demo/pull/1#issuecomment-6197614043), do `may31st` đăng lúc `2026-10-15T16:58:40Z`.
- [Kết quả xác minh](github-pr1-human-verification.json): API GET trả HTTP 200 và nội dung comment khớp checkpoint. [Nội dung comment](github-pr1-human-comment.md) được lưu để đối chiếu.

[Log replay của phiên](audit-pr1-human-replay.log) ghi các bước fetch_pr → analyze → route → human_approval → commit. Sự kiện sau câu trả lời có `reviewer_id=may31st` và `decision=approve`. Dòng pending trước interrupt xuất hiện hai lần do node chạy lại khi resume, đúng với cơ chế LangGraph.

## 5. Dữ liệu kiểm chứng và phạm vi kết quả

[Audit JSON](audit-events.json) có 31 sự kiện tại thời điểm xuất, gồm cả các phiên trước đó. Có thể đối chiếu thêm với [danh sách phiên từ CLI](audit-sessions.log). Các ảnh PNG là ảnh chụp trình duyệt; thư mục bằng chứng không chứa `.env`, token hay database checkpoint.

Các phiên đã lưu xác nhận việc đọc PR, gọi LLM và định tuyến theo confidence. Phiên PR #2 đã đi qua escalation, interrupt/resume, tổng hợp review, đăng comment và audit/replay. PR #1 có comment từ cả nhánh auto_approve và luồng human_approval → Approve → commit.

Bộ bằng chứng vẫn có giới hạn đã nêu ở trên: lần CLI của Exercise 1 cho hai PR vào cùng nhánh, còn phiên chờ duyệt PR #1 dùng analyzer Exercise 1 ghép với các node Exercise 4. Không coi các kết quả này là bằng chứng hoàn tất mọi checkpoint của lab.

Ảnh lỗi token, ảnh phiên dở dang và các bản chụp trạng thái JSON đã được lược bỏ để thư mục gọn hơn. Audit vẫn giữ lịch sử các lần thất bại và thành công.
