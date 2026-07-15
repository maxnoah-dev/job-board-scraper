# 1. Phân tích bài toán (Business Requirements)

**Mục tiêu cốt lõi:** Thu thập tự động, chính xác và liên tục danh sách công việc từ 11 nguồn khác nhau và gom về một nơi duy nhất.

**Các thách thức nghiệp vụ cần giải quyết:**
*   **Sự phân mảnh dữ liệu:** 11 công ty dùng 11 cấu trúc website hoặc hệ thống tuyển dụng (ATS) khác nhau.
*   **Sự thay đổi liên tục:** Giao diện website của các công ty có thể thay đổi bất cứ lúc nào, làm hỏng logic thu thập cũ.
*   **Rào cản kỹ thuật:** Các công ty lớn (như TikTok, Northrop Grumman) có hệ thống chống thu thập dữ liệu (Anti-Bot) rất mạnh.

---

# 2. Giải pháp kiến trúc tổng thể (System Architecture Logic)

Để hệ thống hoạt động trơn tru, chúng ta sẽ áp dụng mô hình **ETL (Extract - Transform - Load)** kết hợp với kiến trúc **Plugin/Adapter**.

## A. Giai đoạn 1: Chuẩn hóa Dữ liệu (Data Standardization)

Mỗi công ty hiển thị dữ liệu một kiểu (ví dụ: TikTok gọi là "Position", công ty khác gọi là "Job Title"). Để quản lý, hệ thống của chúng ta cần một "bản hợp đồng" chung. Dữ liệu đầu ra cuối cùng bắt buộc phải được chuẩn hóa theo cấu trúc sau:

| Trường dữ liệu (Field) | Loại dữ liệu | Ý nghĩa nghiệp vụ | Yêu cầu |
|---|---|---|---|
| **Company_Name** | Văn bản | Tên công ty (Ví dụ: iQmetrix) | Bắt buộc |
| **Job_Title** | Văn bản | Tiêu đề công việc | Bắt buộc |
| **Location** | Văn bản | Nơi làm việc (hoặc Remote) | Bắt buộc |
| **Job_URL** | Liên kết | Đường dẫn trực tiếp để ứng tuyển | Bắt buộc |
| **Date_Posted** | Ngày tháng | Ngày đăng tuyển | Tùy chọn (Nếu có) |
| **Status** | Trạng thái | Đang mở / Đã đóng | Phục vụ việc lọc dữ liệu |

## B. Giai đoạn 2: Phân loại Nguồn (Source Categorization)

Thay vì xử lý 11 công ty giống nhau, chúng ta chia chúng thành 3 nhóm rủi ro và kỹ thuật:

*   **Nhóm Dễ (Sử dụng API/ATS):** OPSWAT, Vancity (thường dùng nền tảng như Greenhouse, Workday). Logic xử lý: Gửi yêu cầu -> Nhận dữ liệu sạch.
*   **Nhóm Trung bình (HTML tĩnh):** Các công ty vừa và nhỏ. Logic xử lý: Tải trang web -> Bóc tách thông tin theo cấu trúc khung.
*   **Nhóm Khó (Website Động & Anti-Bot):** TikTok, Northrop Grumman. Logic xử lý: Cần giả lập hành vi con người (cuộn trang, chờ thời gian tải) để vượt qua tường lửa.

---

# 3. Quy trình Vận hành tự động (Operational Workflow)

Hệ thống sẽ chạy tự động theo một chu trình khép kín hàng ngày (hoặc hàng tuần). Dưới đây là luồng logic từng bước:

1.  **Kích hoạt tự động (Trigger):** Bộ định thời gian (Scheduler) kích hoạt hệ thống vào một giờ cố định (ví dụ: 2h sáng mỗi ngày để tránh làm chậm máy chủ).
2.  **Điều phối Thu thập (Extract):** Bộ điều phối trung tâm gọi lần lượt 11 "Adapter" (đơn vị xử lý riêng) của 11 công ty. Nếu Adapter của Absolute Security bị lỗi, hệ thống ghi nhận lỗi nhưng vẫn tiếp tục chạy 10 công ty còn lại (đảm bảo tính độc lập).
3.  **Làm sạch và Chuẩn hóa (Transform):** Dữ liệu thô thu về được đưa qua màng lọc:
    *   Loại bỏ các công việc trùng lặp (dựa trên `Job_URL`).
    *   Dịch hoặc đồng bộ hóa định dạng ngày tháng.
    *   Điền giá trị mặc định cho các trường bị thiếu.
4.  **Lưu trữ Dữ liệu (Load):** Đưa dữ liệu đã chuẩn hóa vào Cơ sở dữ liệu (Database) hoặc xuất ra file báo cáo (Excel/CSV). Cập nhật trạng thái "Đã đóng" cho những công việc cũ không còn xuất hiện trong lần quét mới nhất.

---

# 4. Quản lý rủi ro & Bảo trì (Risk Management)

Trong nghiệp vụ cào dữ liệu, bảo trì là công việc tốn nhiều thời gian nhất. Hệ thống cần có các cơ chế sau:

*   **Cơ chế Báo cáo lỗi (Alerting):** Nếu giao diện careers của Farm Credit Canada thay đổi khiến hệ thống không tìm thấy chức danh công việc nào (số lượng trả về = 0), hệ thống phải tự động gửi cảnh báo (qua Email/Slack) cho người quản trị thay vì âm thầm lưu dữ liệu rỗng.
*   **Kiểm soát Tần suất (Rate Limiting):** Thiết lập thời gian nghỉ (sleep) khoảng 2-5 giây giữa mỗi lần hệ thống chuyển trang hoặc yêu cầu dữ liệu. Điều này giúp tôn trọng máy chủ của đối tác và tránh việc IP của chúng ta bị chặn do hành vi giống tấn công từ chối dịch vụ (DDoS).

> *Góc nhìn BA này sẽ giúp chúng ta định hình chính xác các bảng trong cơ sở dữ liệu và cấu trúc các hàm khi bước vào giai đoạn viết mã.*