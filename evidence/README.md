# Bằng chứng chạy thật — Day27 HITL PR Review

Các ảnh chụp trực tiếp ứng dụng Streamlit, log Exercise 1 gọi GitHub/LLM thật,
và audit xuất từ SQLite thật. Không thay confidence hoặc dùng API giả lập trong
lần thu thập này. Sau khi người dùng thay token, review PR #2 đã được đăng thành công.

## Kết quả mới nhất: đăng review thành công

- [Comment thật của may31st trên PR #2](https://github.com/VinUni-AI20k/PR-Demo/pull/2#issuecomment-6197316976).
- GitHub trả HTTP **201**, thời điểm `2026-10-15T16:43:43Z` (23:43:43 giờ Việt Nam).
- Graph kết thúc với `final_action = committed_after_escalation`, confidence 50%.
- [Thẻ thành công Streamlit](05-pr2-success.png), [audit trên giao diện](06-pr2-audit-success.png), [comment trên GitHub](07-github-pr2-comment.png.png).
- [Phản hồi tạo comment](github-post-response.json), [xác minh đọc lại comment](github-pr2-verification.json), [kết quả graph](pr2-final-result.json).
- Đã đọc lại comment qua API: tác giả đúng `may31st`, nội dung khớp review đã lưu.
- Bước commit được chạy lại từ checkpoint sau synthesize, giữ nguyên review và Q&A thật;
  không gọi lại LLM hoặc đăng lại các comment đã thành công.

## 1. Exercise 1 chạy bằng CLI

| PR | Confidence lần chạy được lưu | Nhánh |
|---|---|---|
| PR #1 | 70% | human_approval |
| PR #2 | 60% | human_approval |

Log nguyên bản: [PR #1](exercise1-pr1.log), [PR #2](exercise1-pr2.log).
Confidence có thể thay đổi giữa các lần gọi LLM; lần CLI này hai PR vào cùng nhánh,
chưa đạt checkpoint "hai PR vào hai nhánh khác nhau" của riêng lần chạy này.
Không sửa ngưỡng hoặc kết quả để tạo bằng chứng mong muốn.

## 2. Phiên Streamlit PR #2 và phục hồi SQLite

Thread: `b49000a4-79b8-4465-826b-fa9d0ce83411`.

Phiên đã được tạo trước đó và được khôi phục sau khi khởi động lại Streamlit.
UI hiển thị câu hỏi đang chờ, không fetch/phân tích ban đầu lại trên cùng thread.

1. [Màn hình escalation](01-pr2-escalation-before.png): confidence 55%, rủi ro
   MD5, SQL injection, xử lý lỗi mạng, và bốn câu hỏi.
2. [Câu trả lời đã điền](02-pr2-answers.png): trả lời theo hướng review, ghi rõ
   ngữ cảnh chưa xác minh; không bịa kế hoạch triển khai hoặc coi rủi ro đã sửa.
3. Bấm **Submit answers** thật: graph resume, lưu reviewer `may31st`, gọi LLM
   tổng hợp lại; confidence mới là 50%.
4. Graph thử đăng review nhưng GitHub trả HTTP 403. Có một lần thử lại có ghi audit
   để lấy thông báo lỗi API cụ thể; cả hai lần đều thất bại.

[Review tinh chỉnh thực tế](pr2-refined-review.md) có nội dung review và Q&A.
[Log replay](audit-pr2-replay.log) chứng minh luồng:

```text
fetch_pr → analyze → route → escalate (pending)
→ escalate (resume) → synthesize → commit (commit_failed)
```

Dòng pending xuất hiện lại khi node được chạy lại lúc resume, đúng cơ chế interrupt.
Sau khi thay token, cùng phiên này chạy lại node commit và đăng thành công;
log replay hiện giữ cả những lần thất bại và lần thành công cuối.

## 3. Lỗi quyền GitHub đã xác minh

[Phản hồi API trước khi thay token](github-post-response-403.json):

```json
{
  "status": 403,
  "message": "Resource not accessible by personal access token"
}
```

[Màn hình lỗi thật trước khi thay token](03-pr2-github-post-failed.png) được giữ
để ghi lại quá trình xử lý. Token cũ đọc được repo nhưng không tạo được comment.
Người dùng đã thay token và lần thử sau thành công; các ảnh lỗi là lịch sử,
không phải trạng thái cuối cùng.

## 4. Phiên Streamlit PR #1

Thread: `e51f034a-9568-4ca4-b6cc-f48c32d77eb1`.
[Ảnh thực tế](04-pr1-live-escalation.png): confidence 55%, nhánh escalation,
câu hỏi về migration, tests, validation và tài liệu. Phiên này được giữ ở trạng
thái chờ câu trả lời, chưa thử đăng thêm khi đã biết token thiếu quyền.

### Bổ sung sau khi thay token và người dùng xác nhận đăng PR #1

Đã chạy nguyên bản `exercises/exercise_2_hitl.py` với GitHub và LLM thật.
Lần này confidence là **85%**, nên graph tự chọn **auto_approve**, đăng comment
và kết thúc với `auto_approved`. Mặc dù đã chuẩn bị input `approve`, graph không
đi qua interrupt nên input đó không được sử dụng. Đây là bằng chứng nhánh tự
động, không phải bằng chứng đã bấm Approve trong nhánh human_approval.

- [Comment thật của may31st trên PR #1](https://github.com/VinUni-AI20k/PR-Demo/pull/1#issuecomment-6197385176).
- [Log Exercise 2 nguyên bản](exercise2-pr1-live.log).
- [Ảnh comment GitHub](08-github-pr1-comment.png.png).
- [Kết quả xác minh qua API](github-pr1-verification.json).
- [Nội dung comment đã đăng](github-pr1-comment.md).
- Thread: `2fc71c04-b45e-4c00-be66-5d1fa2b81532`; Exercise 2 dùng MemorySaver,
  không ghi thread này vào audit SQLite của Exercise 4.

## 5. Dữ liệu kiểm chứng

- [Audit JSON](audit-events.json): 31 sự kiện tại thời điểm xuất, bao gồm những
  phiên trước đó và sự kiện thật trong lần thu thập này.
- [Danh sách phiên từ CLI](audit-sessions.log).
- Các ảnh PNG là ảnh chụp trình duyệt, không phải mockup.
- Không đóng gói `.env`, token hoặc database checkpoint vào thư mục bằng chứng.

Đã kiểm chứng đọc PR, gọi LLM, định tuyến, giao diện escalation, interrupt/resume,
tổng hợp review, đăng comment GitHub và audit/replay thật cho phiên PR #2.
PR #1 đã có bằng chứng thật cho cả nhánh auto_approve và nhánh human_approval → Approve → commit.

## 6. Bổ sung nhánh human_approval chạy thật

- Thread: `b98141fa-ed3d-481a-a5e0-ea9036ad5716`.
- LLM thật trả confidence **70%**; giữ nguyên ngưỡng 0.58 và 0.73.
- Phiên minh họa ghép **analyzer của Exercise 1** với các node HITL/audit của Exercise 4 bằng [script tái hiện](run_human_approval_demo.py). Đây là cấu hình tích hợp minh họa; không khẳng định analyzer mặc định của Exercise 4 cho ra 70%. Các lần chạy analyzer mặc định trước đó cho 55% và đã dừng trước route.
- Mở checkpoint trên Streamlit, quan sát thẻ chờ duyệt, điền feedback và bấm **Approve**. Graph resume, đăng comment thật và kết thúc với `final_action=committed`, `human_choice=approve`.
- [Comment mới trên PR #1](https://github.com/VinUni-AI20k/PR-Demo/pull/1#issuecomment-6197614043), tài khoản `may31st`, tạo lúc `2026-10-15T16:58:40Z`.
- API GET trả **200**, nội dung comment khớp checkpoint: [kết quả xác minh](github-pr1-human-verification.json), [nội dung comment](github-pr1-human-comment.md), [checkpoint cuối](pr1-human-final.json).
- [Trước Approve](09-pr1-human-approval-before.png), [đăng thành công](10-pr1-human-approval-success.png), [audit trên giao diện](11-pr1-human-approval-audit.png).
- [Replay phiên](audit-pr1-human-replay.log): fetch_pr → analyze → route → human_approval → commit; sự kiện sau câu trả lời ghi `reviewer_id=may31st`, `decision=approve`. Dòng pending trước interrupt xuất hiện hai lần do node chạy lại khi resume, đúng cơ chế LangGraph.

Lần bổ sung này chỉ lưu bằng chứng; không commit, push hay gửi form nộp bài.
