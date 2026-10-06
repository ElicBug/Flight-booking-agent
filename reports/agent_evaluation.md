# Báo cáo: Đánh giá hiệu quả các mẫu thiết kế Agent đặt vé máy bay

**Ngày tổng hợp:** 06-10-2026

**Nguồn số liệu:** các file `runs/react.jsonl`, `runs/plan_execute.jsonl`, `runs/hybrid.jsonl` trong workspace.

## 1. Kịch bản thử nghiệm

### Kết quả CLI đã ghi nhận

Mỗi kiến trúc hiện có một lượt chạy được lưu. ReAct hoàn thành đặt vé; Plan-then-Execute và Hybrid đều dừng sau khi Harness từ chối ngày bay không khớp constraint.

| Kịch bản quan sát được | Mẫu | Kết quả thực tế |
|---|---|---|
| Tìm chuyến, kiểm tra ghế, đặt và thanh toán | ReAct | Thành công; `get_booking` được Harness xác minh. Trace: `search_flights`, `check_seat` x2, `book_seat`, `pay`, `get_booking`. |
| Kế hoạch tìm chuyến không khớp ngày constraint | Plan-then-Execute | Bị Harness chặn tại `search_flights`; chưa đặt vé. |
| Kế hoạch Hybrid tìm chuyến không khớp ngày constraint | Hybrid | Bị Harness chặn tại `search_flights`; chưa đặt vé. |

Các unit test Harness kiểm tra riêng: vi phạm ngày bị chặn; yêu cầu duyệt và tiếp tục booking/payment; từ chối duyệt; giới hạn lượt/token; phát hiện action lặp; bế tắc; phân giải dữ liệu tham chiếu trong kế hoạch. Đây là test logic, không phải các lượt benchmark LLM độc lập.

Kịch bản ghế hết chỗ rồi tự chọn chuyến khác và kịch bản không có chuyến phù hợp chưa có lượt CLI được lưu. Không có dữ liệu thực nghiệm để khẳng định các agent đã xử lý thành công hai tình huống đó.

## 2. Đánh giá chi tiết từng kiến trúc

### A. Mẫu ReAct

**Hành vi thực tế:** một lượt đã hoàn tất booking. Log ghi 4.344 token, 8 bước Harness, 23,850 giây và 6 lần gọi tool được lưu trong trace. Thứ tự tool là tìm chuyến, kiểm tra hai ghế, đặt ghế, thanh toán và lấy booking để xác minh. Mục tiêu được Harness xác nhận.

**Điểm mạnh:** mỗi observation có thể ảnh hưởng tới hành động kế tiếp; phù hợp khi số bước không biết trước hoặc seat/inventory có thể thay đổi. Trong lượt ghi nhận, agent đã kiểm tra hơn một ghế trước khi tiếp tục.

**Điểm yếu và rủi ro:** ReAct có thể tốn token do phải gửi lịch sử qua nhiều lượt; LoopDetector và ngân sách giới hạn rủi ro lặp nhưng lượt chạy này không ghi nhận loop. Log không lưu số lần gọi model/vòng suy luận hoặc token theo từng vòng, nên không thể tính mức token tăng sau mỗi vòng. `tool_steps` lớn hơn số tool trong trace vì bộ đếm Harness tính cả lần xin duyệt và lần chạy lại sau duyệt; hai metric này không nên hiểu là cùng một đại lượng.

### B. Mẫu Plan-then-Execute

**Hành vi thực tế:** nội dung kế hoạch thô không được lưu. Trace ghi một `search_flights`, tổng 531 token, 3,194 giây; Harness chặn vì `date_constraint_violation`. Không có booking được xác minh.

**Điểm mạnh:** kế hoạch có cấu trúc có thể được trình bày để người dùng duyệt trước khi thực thi; đầu ra ghi nhận trong lượt này dùng ít token hơn ReAct. Harness vẫn kiểm tra từng bước, không tin kế hoạch là dữ liệu sự thật.

**Điểm yếu:** một kế hoạch phụ thuộc nhiều bước có thể mất hiệu lực khi kết quả thực tế khác dự kiến. Lượt hiện tại dừng ngay tại tìm chuyến sai constraint, nên chưa quan sát được khả năng phục hồi của kế hoạch sau lỗi `book_seat`. Vì raw plan không được lưu, không thể đánh giá chính xác kế hoạch ban đầu gồm những bước nào.

### C. Mẫu Lai / Hybrid

**Hành vi thực tế:** trace có một `search_flights`, 442 token, 2,574 giây; Harness chặn lỗi ngày và booking không hoàn tất. Log hiện không ghi riêng stage review, nội dung nhận xét hoặc số lần replan, nên không thể xác nhận/định lượng việc đổi kế hoạch từ metric này.

**Điểm mạnh:** thiết kế chia kế hoạch thành nhóm bước rồi review observation, tạo cơ hội điều chỉnh giữa quy trình dài mà không cần gọi model sau mọi tool.

**Điểm yếu:** thêm lượt review và trạng thái kế hoạch làm tăng độ phức tạp khi debug; nếu kế hoạch sai từ bước đầu thì vẫn phải dựa vào bước đánh giá để phục hồi. Ở lượt thực tế này, không có booking thành công và chưa có metric chứng minh Hybrid đã replan hiệu quả.

## 3. Kết luận

### So sánh số liệu hiện có

| Mẫu | Số lượt | Token trung bình/lượt | Thời gian trung bình | Bước Harness trung bình | Thành công quan sát được |
|---|---:|---:|---:|---:|---:|
| ReAct | 1 | 4.344 | 23,850 giây | 8 | 1/1 (100%) |
| Plan-then-Execute | 1 | 531 | 3,194 giây | 1 | 0/1 (0%) |
| Hybrid | 1 | 442 | 2,574 giây | 1 | 0/1 (0%) |

**Lưu ý:** đây là mô tả ba lượt quan sát, không phải benchmark đủ lớn. Tỷ lệ hoàn thành 1/1 không dự báo được tỷ lệ thực tế. File metric chưa lưu tên model/provider, constraint đầy đủ, số lần gọi model, kế hoạch thô, số lần review/replan hoặc token theo từng lượt. Vì vậy chưa thể khẳng định ba lần chạy có cấu hình hoàn toàn tương đương, hoặc so sánh chi phí trên mỗi vòng.

**Khuyến nghị:** với phiên bản và bằng chứng hiện có, dùng ReAct làm baseline vì đây là mẫu duy nhất hoàn tất booking được Harness xác minh. Hybrid là hướng cân bằng đáng thử cho inventory biến động, nhưng chỉ nên khuyến nghị sau khi sửa lỗi ngày ở đầu vào kế hoạch và ghi được review/replan; lượt hiện tại chưa chứng minh ưu thế đó. Plan-then-Execute phù hợp hơn khi quy trình ổn định và kế hoạch được tạo từ dữ liệu đáng tin cậy.

Để kết luận hiệu quả chắc hơn, chạy cùng model, cùng constraints và cùng mock inventory ít nhất 10 kịch bản, lặp mỗi kịch bản 3 lần. Bổ sung log số lần gọi model, token từng lượt, raw plan/review đã loại dữ liệu nhạy cảm, replan count và kết quả xác minh booking.