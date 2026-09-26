"""Apply author-approved runtime-text repairs from the v1 leakage audit.

``data/benchmark.csv`` is the canonical runtime-text source.  The legacy
``extraction.json`` copy is synchronized here as well so the
normal canonicalization and gold-repair scripts do not report a stale query.

Case 125 includes the subsequently approved scenario and reference
recalculation.  Its timeline places B's death after M's death so B's first-line
heirs are closed and the allocation has a unique result.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = PROJECT_ROOT / "data" / "benchmark.csv"
LEGACY_EXTRACTION_PATH = PROJECT_ROOT / "data" / "extraction.json"


REPLACEMENTS: dict[str, list[tuple[str, str]]] = {
    "3": [
        (
            "Qua quá trình điều tra, Tòa án xác định di chúc của ông Nguyễn Văn A không hợp pháp.",
            "Trong phạm vi tình huống, giả định di chúc của ông Nguyễn Văn A không hợp pháp.",
        )
    ],
    "5": [
        (
            "Qua điều tra, Tòa án xác định khối tài sản của ông Nguyễn Văn A và bà Trần Thị B là 500.000.000 đồng.",
            "Khối tài sản chung của ông Nguyễn Văn A và bà Trần Thị B được xác định là 500.000.000 đồng.",
        ),
        (
            "Trước khi chết, ông Nguyễn Văn A để lại bản di chúc với nội dung cho anh Nguyễn Văn T thừa hưởng toàn bộ tài sản do ông Nguyễn Văn A để lại.",
            "Trước khi chết, ông Nguyễn Văn A để lại bản di chúc hợp pháp và có hiệu lực với nội dung cho anh Nguyễn Văn T thừa hưởng toàn bộ tài sản do ông Nguyễn Văn A để lại. Trong phạm vi tình huống, bà Trần Thị B và bà Lê Thị C đều được xác định là vợ hợp pháp của ông Nguyễn Văn A tại thời điểm ông chết và thuộc diện người hưởng di sản không phụ thuộc vào nội dung di chúc.",
        ),
    ],
    "8": [
        (
            "Ngày 08/01/2008, ông Nguyễn Văn Hậu chết đột ngột và để lại di chúc miệng hợp pháp, được nhiều người chứng kiến và có ghi chép lại, với nội dung để tài sản cho bà Lê Thị Thủy, Nguyễn Văn Sơn và Nguyễn Thị Xuân, mỗi người một phần bằng nhau.",
            "Ngày 08/01/2008, ông Nguyễn Văn Hậu chết đột ngột. Trước khi chết, ông thể hiện ý chí cuối cùng trước mặt hai người làm chứng, để tài sản cho bà Lê Thị Thủy, Nguyễn Văn Sơn và Nguyễn Thị Xuân, mỗi người một phần bằng nhau. Ngay sau đó, hai người làm chứng ghi chép lại đầy đủ lời di chúc và cùng ký tên. Trong thời hạn 05 ngày, chữ ký của hai người làm chứng được cơ quan có thẩm quyền chứng thực.",
        ),
    ],
    "9": [
        (
            "Năm 2007, bà Lê Thị Miên mất, trước khi chết bà Lê Thị Miên có để lại di chúc cho bà Lê Thị Trâm là em gái 1/2 số tài sản của mình.",
            "Năm 2007, bà Lê Thị Miên mất, trước khi chết bà Lê Thị Miên để lại di chúc hợp pháp và có hiệu lực cho bà Lê Thị Trâm là em gái 1/2 số tài sản của mình.",
        ),
    ],
    "10": [
        (
            "Năm 2007, bà Lê Thị Miên mất, trước khi chết bà Lê Thị Miên có để lại di chúc cho bà Lê Thị Trâm là em gái một nửa số tài sản của mình nhưng bà Lê Thị Trâm khước từ nhận di sản thừa kế.",
            "Năm 2007, bà Lê Thị Miên mất, trước khi chết bà Lê Thị Miên để lại di chúc hợp pháp và có hiệu lực cho bà Lê Thị Trâm là em gái một nửa số tài sản của mình. Trong thời hạn sáu tháng kể từ ngày mở thừa kế, bà Lê Thị Trâm tự nguyện từ chối nhận di sản bằng văn bản, đã thông báo hợp lệ cho những người liên quan và việc từ chối không nhằm trốn tránh nghĩa vụ tài sản.",
        ),
    ],
    "12": [
        (
            "Qua điều tra, Tòa án xác định được tài sản chung hợp nhất của ông Nguyễn Văn Sáu và bà Lê Thị Son là 80.000.000 đồng.",
            "Tài sản chung hợp nhất của ông Nguyễn Văn Sáu và bà Lê Thị Son được xác định là 80.000.000 đồng.",
        )
    ],
    "13": [
        (
            "Ông Nguyễn Văn A qua đời có để lại di chúc cho anh Nguyễn Văn C 1/2 di sản, cho bà Trần Thị B và bà Lê Thị T mỗi người 1/4 di sản.",
            "Ông Nguyễn Văn A qua đời có để lại di chúc hợp pháp và có hiệu lực cho anh Nguyễn Văn C 1/2 di sản, cho bà Trần Thị B và bà Lê Thị T mỗi người 1/4 di sản. Trong phạm vi tình huống, bà Trần Thị B và bà Lê Thị T đều được xác định là vợ hợp pháp của ông Nguyễn Văn A tại thời điểm ông chết.",
        ),
    ],
    "28": [
        (
            "lập một bản di chúc hoàn toàn hợp pháp",
            "lập một bản di chúc hợp pháp",
        )
    ],
    "41": [
        (
            "Bà Trần Thị D và Nguyễn Văn E yêu cầu được hưởng thừa kế bắt buộc, còn Nguyễn Văn C yêu cầu được hưởng thừa kế thế vị thay cha là Nguyễn Văn B.",
            "Bà Trần Thị D, Nguyễn Văn E và Nguyễn Văn C đều yêu cầu được chia một phần di sản.",
        )
    ],
    "48": [
        (
            "Ông Nguyễn Văn P có vợ là bà Trần Thị V, không có con, và không còn người thừa kế hàng thứ nhất nào khác ngoài bà Trần Thị V.",
            "Cha mẹ ông Nguyễn Văn P đều đã chết trước ông; ông Nguyễn Văn P không có con và tại thời điểm ông chết chỉ có vợ là bà Trần Thị V.",
        )
    ],
    "58": [
        (
            "Thực tế, cụ X chưa từng làm thủ tục tặng cho ai, nên Tòa án xác định quyền sử dụng đất vẫn của cụ X với diện tích đo đạc hiện trạng là 261,4m2 cùng ngôi nhà cấp 4 xây năm 1976, định giá 0 đồng.",
            "Cụ X chưa từng làm thủ tục tặng cho quyền sử dụng đất. Trong phạm vi phân chia, quyền sử dụng 261,4m2 đất được xác định thuộc di sản của cụ X. Ngôi nhà cấp 4 xây năm 1976 được định giá 0 đồng.",
        ),
        (
            "Bà C1 (chết năm 2017) và chồng (chết năm 1987) có 5 người con:",
            "Bà C1 (chết năm 2017, không để lại di chúc) và chồng (chết năm 1987) có 5 người con:",
        ),
    ],
    "66": [
        (
            "Phía bà Trần Thị T và những người thừa kế của bà Huỳnh Kim H không đồng ý với lời khai của bà Trần Thị G",
            "Phía bà Trần Thị T cùng N, T1, Đ, T2 và Q không đồng ý với lời khai của bà Trần Thị G",
        ),
        (
            "Năm 2021, bà Huỳnh Kim H qua đời, để lại các con là N, T1, Đ, T2 và Q.",
            "Năm 2021, bà Huỳnh Kim H qua đời không để lại di chúc; cha mẹ và chồng bà đều đã chết trước bà, và năm người con N, T1, Đ, T2, Q là toàn bộ người thuộc hàng thừa kế thứ nhất của bà.",
        ),
        (
            "Phân chia di sản của bà T8.",
            "Hãy lần lượt phân chia di sản của bà T8 và phần tài sản bà Huỳnh Kim H nhận được từ di sản của bà T8.",
        ),
    ],
    "69": [
        ("Cụ M (chết năm 1990)", "Cụ M (chết trước ngày 10/09/1990)")
    ],
    "79": [
        (
            "Phía những người thừa kế của ông T không đồng ý, cho rằng",
            "Phía gia đình ông T không đồng ý, cho rằng",
        )
    ],
    "87": [
        (
            "Phía các cháu là con của những người con đã mất yêu cầu được hưởng thừa kế thế vị đối với suất của bố/mẹ mình.",
            "Phía các cháu là con của những người con đã mất yêu cầu nhận phần tương ứng với phần của bố hoặc mẹ mình.",
        )
    ],
    "90": [
        (
            "Cụ Nguyễn Đức M (chết năm 1990)",
            "Cụ Nguyễn Đức M (chết trước ngày 10/09/1990)",
        )
    ],
    "92": [
        (
            "T quản lý tài sản từ năm 2001 và được Tòa án xác định có công sức quản lý, tôn tạo tài sản tương đương 20% tổng giá trị khối di sản (1.797.518.795 đồng).",
            "T quản lý tài sản từ năm 2001. Trong phạm vi bài toán, khoản ghi nhận công sức quản lý và tôn tạo của T được ấn định bằng 20% tổng giá trị khối tài sản, tương đương 1.797.518.795 đồng.",
        )
    ],
    "98": [
        (
            "cụ Huỳnh Thị T5 (mất năm 1996)",
            "cụ Huỳnh Thị T5 (mất trước ngày 01/07/1996)",
        )
    ],
    "117": [
        (
            "Cụ Tụng và cụ Thìn sinh được 5 người con gồm: Tý (chết lúc 2 tuổi), ông Thuyết (chết 2017), ông Tuân, bà Mùi và bà Hương. Ông Thuyết và bà Lược (chết 2000) là vợ chồng hợp pháp, sinh được 5 người con: Thiêm (chết lúc 2 tuổi), anh Th (Thuỳ), chị Mỵ, anh Tiêu (chết 2011, có hai con là Cường, Mạnh) và anh T. Ngoài ra, ông Thuyết chung sống không đăng ký kết hôn với bà Lụa và sinh được anh Thiên. Tài sản tranh chấp là một thửa đất có diện tích đo đạc thực tế 629,1m2 (định giá 7.000.000 đồng/m2) do ông Thuyết đứng tên Giấy chứng nhận quyền sử dụng đất từ năm 1997. Anh T khởi kiện yêu cầu chia di sản thừa kế của ông Thuyết và bà Lược đối với thửa đất, trong đó di sản của ông Thuyết yêu cầu chia theo di chúc năm 2008. Bị đơn (anh Th) và các người liên quan không đồng ý, cho rằng đất là của tổ tiên để lại, ông Thuyết chỉ đứng tên đại diện để lo thờ cúng theo biên bản họp gia đình năm 2014 và ông Thuyết đã có văn bản hủy bỏ di chúc năm 2008. Bị đơn yêu cầu hủy Giấy chứng nhận quyền sử dụng đất của ông Thuyết. Chia di sản của Thuyết và Lược",
            "Ông Thuyết và bà Lược là vợ chồng hợp pháp, có bốn người con còn sống đến năm 2000 là Th, Mỵ, Tiêu và T. Người con Thiêm đã chết khi còn nhỏ trước năm 2000 và không có con. Ông Thuyết và bà Lược cùng sở hữu một thửa đất diện tích 629,1m2, trị giá 4.403.700.000 đồng; mỗi người sở hữu một nửa. Năm 2000, bà Lược chết không để lại di chúc. Khi bà Lược chết, cha mẹ bà đều đã chết và bà chỉ có chồng cùng bốn người con Th, Mỵ, Tiêu và T thuộc hàng thừa kế thứ nhất. Năm 2011, Tiêu chết không để lại di chúc. Khi Tiêu chết, mẹ đã chết trước, Tiêu không có vợ và chỉ có cha là Thuyết cùng hai người con Cường, Mạnh thuộc hàng thừa kế thứ nhất. Ông Thuyết còn có người con là Thiên với bà Lụa; ông Thuyết và bà Lụa chung sống nhưng không đăng ký kết hôn. Năm 2008, ông Thuyết lập di chúc. Năm 2014, khi còn minh mẫn và tự nguyện, ông Thuyết lập văn bản hợp pháp hủy bỏ toàn bộ di chúc năm 2008 và sau đó không lập di chúc khác. Năm 2017, ông Thuyết chết; cha mẹ và vợ ông đều đã chết trước ông. Những người con còn sống của ông là Th, Mỵ, T và Thiên; Tiêu chết trước ông và có hai con là Cường, Mạnh. Các bên không có nghĩa vụ tài sản hoặc chi phí phải khấu trừ và thống nhất nhận giá trị bằng tiền. Hãy lần lượt phân chia di sản của bà Lược, Tiêu và ông Thuyết.",
        )
    ],
    "122": [
        (
            "Cụ Trần Văn C (mất năm 2009) và cụ Nguyễn Thị B (mất năm 1978)",
            "Cụ Trần Văn C (mất năm 2009, không để lại di chúc) và cụ Nguyễn Thị B (mất năm 1978)",
        ),
    ],
    "83": [
        (
            "Bà C1 chết sau cụ Đ1, để lại chồng là ông C và 4 người con (L, T4, N, T5).",
            "Năm 2018, bà C1 chết không để lại di chúc, để lại chồng là ông C và 4 người con L, T4, N, T5. Mẹ bà C1 là cụ D còn sống nhưng đã từ chối nhận di sản của bà C1 bằng văn bản hợp lệ trước khi phân chia; cha bà C1 là cụ Đ1 đã chết trước bà.",
        ),
        (
            "Các anh chị em khác thống nhất chia di sản của cụ Đ1 theo pháp luật.",
            "Các anh chị em khác thống nhất chia di sản của cụ Đ1 theo pháp luật. Hãy lần lượt phân chia di sản của cụ Đ1 và phần tài sản bà C1 nhận được từ di sản của cụ Đ1.",
        ),
    ],
    "103": [
        (
            "Năm người con còn sống được hưởng thừa kế gồm:",
            "Năm người con còn sống gồm:",
        )
    ],
    "105": [
        (
            "Cụ Võ Văn N3 mất năm 2014, để lại khối di sản thừa kế trị giá 10.446.300.000 đồng.",
            "Cụ Võ Văn N3 mất năm 2014, không để lại di chúc và để lại khối di sản thừa kế trị giá 10.446.300.000 đồng.",
        ),
        (
            "Võ Văn P, Võ Văn B1 (đã chết) và Võ Văn S (đã chết).",
            "Võ Văn P, Võ Văn B1 (đã chết trước cụ N3) và Võ Văn S (đã chết trước cụ N3).",
        ),
    ],
    "109": [
        (
            "Chia thừa kế của cụ H1 và G",
            "Hãy lần lượt phân chia di sản của cụ Đỗ Thị G và phần tài sản bà Phạm Thị H2 nhận được từ di sản của cụ Đỗ Thị G.",
        ),
    ],
    "125": [
        (
            "Ông Hoàng Văn S2 (chết năm 2010) và bà Triệu Thị M (chết năm 2018) có 7 người con là Hoàng Thị D (chết năm 2021), Hoàng Thị V, Hoàng Thị Tr, Hoàng Thị T, Hoàng Thị T4 (chết năm 2004), Hoàng Văn B (chết năm 2017) và Hoàng Lệ T1.",
            "Ông Hoàng Văn S2 (chết năm 2010) và bà Triệu Thị M (chết năm 2018, không để lại di chúc) có 7 người con là Hoàng Thị D (chết năm 2021), Hoàng Thị V, Hoàng Thị Tr, Hoàng Thị T, Hoàng Thị T4 (chết năm 2004), Hoàng Văn B (chết năm 2019, không để lại di chúc) và Hoàng Lệ T1.",
        ),
        (
            "Anh B có vợ là Hoàng Thị H và con chung là Hoàng Việt V1.",
            "Anh B có vợ là Hoàng Thị H và một người con duy nhất là Hoàng Việt V1. Khi anh B chết, cha mẹ anh đều đã chết và anh không còn người nào khác thuộc hàng thừa kế thứ nhất.",
        ),
        (
            "Lúc sinh thời, ông S2 và bà M tạo lập được khối tài sản chung là các diện tích đất đã bị Nhà nước thu hồi, được bồi thường tổng số tiền 405.240.752 đồng.",
            "Lúc sinh thời, ông S2 và bà M tạo lập được khối tài sản chung là các diện tích đất đã bị Nhà nước thu hồi, được bồi thường tổng số tiền 405.240.752 đồng; mỗi người sở hữu một nửa khối tài sản này.",
        ),
        (
            "Năm 2009, ông S2 lập di chúc để lại toàn bộ tài sản cho gia đình anh B. Tuy nhiên, do ông S2 tự ý định đoạt cả phần tài sản của bà M nên di chúc bị tuyên vô hiệu toàn bộ.",
            "Năm 2009, ông S2 lập di chúc hợp pháp với nội dung định đoạt toàn bộ khối tài sản chung cho bà M và anh B, mỗi người một nửa. Trong phạm vi tình huống, giả định di chúc chỉ có hiệu lực đối với một nửa khối tài sản thuộc sở hữu của ông S2; phần có hiệu lực này được chia đều cho bà M và anh B.",
        ),
        (
            "Bà T khởi kiện yêu cầu chia di sản thừa kế của ông S2 và bà M là số tiền 405.240.752 đồng theo pháp luật. Bà H phản đối vì cho rằng tài sản đã được định đoạt theo di chúc. Hãy phân chia di sản thừa kế của ông S2 và bà M",
            "Bà T khởi kiện yêu cầu phân chia số tiền 405.240.752 đồng. Bà H cho rằng cần thực hiện phần di chúc có hiệu lực của ông S2. Hãy phân chia di sản của ông S2, bà M và phần tài sản anh B nhận được trong tình huống này. Phần của bà D phát sinh khi bà M chết được ghi nhận cho bà D; không tiếp tục giải quyết di sản của bà D.",
        ),
    ],
    "127": [
        (
            "Ông L xuất trình một bản di chúc của cụ C, tuy nhiên tòa án xác định di chúc không hợp pháp.",
            "Ông L xuất trình một bản di chúc của cụ C. Trong phạm vi tình huống, giả định bản di chúc này không hợp pháp.",
        )
    ],
    "128": [
        (
            "Bà L trước khi chết đã lập hai bản di chúc hợp pháp để lại toàn bộ tài sản của mình (gồm 1/2 thửa 292 và 1/2 thửa 293) cho ông S.",
            "Theo dữ kiện được xác nhận trong tình huống, trước khi chết bà L đã lập hai bản di chúc hợp pháp và có hiệu lực, để lại toàn bộ tài sản của mình (gồm 1/2 thửa 292 và 1/2 thửa 293) cho ông S.",
        ),
        (
            "ông H1 (chết năm 2022, có vợ là bà T7 và 3 con là Â2, C, A1)",
            "ông H1 (chết năm 2022 không để lại di chúc; khi chết, cha mẹ ông đều đã chết và ông chỉ có vợ là bà T7 cùng 3 người con Â2, C, A1 thuộc hàng thừa kế thứ nhất)",
        ),
        (
            "Hãy phân chia di sản của ông T6 và bà L.",
            "Hãy phân chia di sản của ông T6, bà L và phần tài sản ông H1 đã nhận từ di sản của ông T6.",
        ),
    ],
    "138": [
        (
            "Hai cụ qua đời không để lại di chúc hợp pháp.",
            "Cụ C2 không để lại di chúc. Ông N xuất trình một di chúc và giấy ủy quyền viết tay được cho là của cụ N2; trong phạm vi tình huống, giả định các văn bản này không đáp ứng điều kiện có hiệu lực.",
        ),
        (
            "Ông N không đồng ý, đưa ra một di chúc và giấy ủy quyền viết tay của cụ N2 để yêu cầu được hưởng toàn bộ nhà đất nhằm thờ cúng.",
            "Ông N không đồng ý và căn cứ vào các văn bản viết tay nêu trên để yêu cầu được nhận toàn bộ nhà đất nhằm thờ cúng.",
        ),
        (
            "điều kiện có hiệu lực.Tài sản chung",
            "điều kiện có hiệu lực. Tài sản chung",
        ),
    ],
    "136": [
        (
            "T và X đã xây dựng nhà kiên cố trên phần đất này từ năm 2020.",
            "T và X đã xây dựng nhà kiên cố trên phần đất này từ năm 2020. Trong phạm vi tình huống, các bên thống nhất trích từ di sản một khoản công sức bằng 1/8 giá trị di sản cho bà X; 7/8 giá trị còn lại được chia thành bảy suất thừa kế theo pháp luật.",
        ),
    ],
    "129": [
        (
            "ông H4 (chết năm 2004, có vợ là bà N và 5 con gái N3, T1, H2, L1, T2)",
            "ông H4 (chết năm 2004 không để lại di chúc; cha mẹ đều chết trước ông; vợ là bà N và 5 con gái N3, T1, H2, L1, T2 là toàn bộ người thuộc hàng thừa kế thứ nhất của ông)",
        ),
        (
            "Hãy phân chia di sản của cụ T3.",
            "Hãy lần lượt phân chia di sản của cụ T3 và phần tài sản ông H4 nhận được từ di sản của cụ T3.",
        ),
    ],
    "145": [
        (
            "V (mất 2022, có 4 người thừa kế là V1, V2, V3 và V4)",
            "V (mất năm 2022; V1, V2, V3 và V4 là những người thuộc nhóm vợ, chồng hoặc con của V, nhưng nguồn không nêu rõ quan hệ cụ thể của từng người)",
        ),
        (
            "Nay 7 người con (gồm cả người thừa kế của Đ và V) khởi kiện",
            "Nay 7 nhánh gia đình (gồm các con của Đ và nhóm vợ, chồng hoặc con của V) khởi kiện",
        ),
    ],
    "140": [
        (
            "Quá trình sinh sống, vợ chồng ông H1 có công chăm sóc, tôn tạo di sản của cụ T5, được các bên thống nhất trích thưởng bằng 1 suất thừa kế.",
            "Quá trình sinh sống, vợ chồng ông H1 có công chăm sóc, tôn tạo di sản của cụ T5, được các bên thống nhất trích thưởng bằng 1 suất thừa kế. Mọi phần tài sản được giao hoặc trích thưởng cho vợ chồng ông H1 và bà X trong tình huống này thuộc sở hữu của hai người theo phần bằng nhau.",
        ),
    ],
    "149": [
        (
            "Cụ Lê Tín Đ (chết năm 1996)",
            "Cụ Lê Tín Đ (chết trước ngày 01/07/1996)",
        )
    ],
}


# Once a full name has been introduced, use that same surface form throughout
# the query. This reduces accidental entity duplication during extraction and
# keeps settlement recipient identifiers aligned with runtime text.
NAME_STANDARDIZATIONS: dict[str, list[tuple[str, str]]] = {
    "80": [
        (r"\bcụ C1\b", "cụ Đỗ Hữu C1"),
        (r"\bcụ C2\b", "cụ Đỗ Thị C2"),
        (r"\bbà M2\b", "bà Đỗ Thị M2"),
        (r"\bbà M và M1\b", "bà Đỗ Thị M và bà Đỗ Thị M1"),
    ],
    "81": [
        (r"\bcụ T5\b", "cụ Lê Thị T5"),
        (r"\bông S\b", "ông Nguyễn Văn S"),
        (r"\bông T1\b", "ông Nguyễn Văn T1"),
        (r"\bông T2\b", "ông Nguyễn Văn T2"),
        (r"\bAnh H\b", "Anh Nguyễn Văn H"),
        (r"\banh H\b", "anh Nguyễn Văn H"),
        (r"\banh Q\b", "anh Nguyễn Văn Q"),
        (r"Các ông bà M, S2, T3, T1, Q", "Bà Nguyễn Thị M, bà Nguyễn Thị S2, ông Nguyễn Văn T3, ông Nguyễn Văn T1 và anh Nguyễn Văn Q"),
    ],
    "82": [
        (r"\bông Th\b", "ông Nguyễn Văn Th"),
        (r"\bông S\b", "ông Nguyễn Ngọc S"),
        (r"\bbà H1\b", "bà Nguyễn Thị H1"),
        (r"\bbà H2\b", "bà Nguyễn Thị H2"),
        (r"\bông H3\b", "ông Nguyễn H3"),
        (r"\bbà H4\b", "bà Nguyễn Thị H4"),
    ],
    "103": [(r"\bông Đ1\b", "ông Nguyễn Văn Đ1")],
    "109": [
        (r"\bcụ G\b", "cụ Đỗ Thị G"),
        (r"\bbà H2\b", "bà Phạm Thị H2"),
        (r"\bbà T1\b", "bà Phạm Thị T1"),
        (r"\bông T\b", "ông Phạm Văn T"),
        (r"\bông N1\b", "ông Phạm Văn N1"),
        (r"\bông N\b", "ông Phạm Văn N"),
    ],
    "117": [(r"\bTh\b", "Thuỳ")],
    "120": [(r"\bbà K\b", "bà Lê Thị K")],
    "125": [
        (r"\bbà M\b", "bà Triệu Thị M"),
        (r"\bchị T4\b", "chị Hoàng Thị T4"),
        (r"\banh B\b", "anh Hoàng Văn B"),
        (r"\bbà H\b", "bà Hoàng Thị H"),
        (r"\bbà T\b", "bà Hoàng Thị T"),
        (r"\bbà D\b", "bà Hoàng Thị D"),
    ],
    "140": [
        (r"\bcụ T5\b", "cụ Phan Ngọc T5"),
        (r"\bcụ T6\b", "cụ Trần Thị T6"),
    ],
    "144": [
        (r"\bcụ X\b", "cụ Phạm Văn X"),
        (r"\bcụ T4\b", "cụ Lê Thị T4"),
        (r"\bbà Tuyết H\b", "bà Phạm Thị Tuyết H"),
        (r"\bông B\b", "ông Phạm Văn B"),
        (r"\bông T\b", "ông Phạm Văn T"),
    ],
    "148": [
        (r"\bông S\b", "ông Nguyễn Văn S"),
        (r"\bông L\b", "ông Nguyễn Văn L"),
    ],
    "149": [
        (r"\bcụ Đ\b", "cụ Lê Tín Đ"),
        (r"\bcụ L\b", "cụ Trần Thụy L"),
        (r"\bông Ch\b", "ông Lê Quốc Ch"),
        (r"\bbà B\b", "bà Lê Thị Hòa B"),
        (r"\bông Ph\b", "ông Lê Tấn Ph"),
        (r"(?<!Lê Thanh )\bL1\b", "Lê Thanh L1"),
    ],
}


REFERENCE_OVERRIDES = {
    "9": {
        "Expected_Distribution": (
            "Nguyễn Văn Du: 87777778; Nguyễn Thị Thảo: 87777778; "
            "Nguyễn Thị Chi: 87777777; Lê Thị Trâm: 131666667"
        ),
    },
    "13": {
        "Expected_Distribution": (
            "Trần Thị B: 256666667; Lê Thị T: 256666667; "
            "Nguyễn Văn D: 46666667; Nguyễn Thị E: 46666667; "
            "Nguyễn Thị F: 46666667; Nguyễn Văn H: 46666667; "
            "Nguyễn Văn K: 46666666; Nguyễn Văn P: 46666666; "
            "Nguyễn Thị N: 23333333; Nguyễn Văn G: 23333333"
        ),
    },
    "66": {
        "Expected_Articles": "611; 612; 613; 614; 649; 650; 651; 660",
        "Expected_Distribution": (
            "Trần Thị T: 4751866600; Trần Thị G: 4751866600; "
            "N: 950373320; T1: 950373320; Đ: 950373320; "
            "T2: 950373320; Q: 950373320"
        ),
    },
    "78": {
        "Expected_Articles": "611; 612; 613; 614; 649; 650; 651; 660",
        "Expected_Distribution": "Phạm Văn N: 426575000; Phạm Văn T: 1706300000",
    },
    "83": {
        "Expected_Articles": "611; 612; 613; 614; 620; 649; 650; 651; 660",
    },
    "104": {
        "Expected_Distribution": "Th: 1634628958; T: 326925792",
    },
    "105": {
        "Expected_Distribution": (
            "Võ Văn T: 2007123077; Võ Văn B: 803561539; "
            "Võ Văn T2: 803561539; Võ Văn D: 803561539; "
            "Võ Thị H: 803561539; Võ Thị R: 803561539; "
            "Võ Văn M: 401780769; Võ Văn Minh N2: 401780769; "
            "Võ Thị V: 160712308; Võ Thị T3: 160712308; "
            "Võ Thị H1: 160712308; Võ Văn Thanh L: 160712307; "
            "Võ Văn K: 160712307; Nguyễn Thị L1: 703561538; "
            "Nguyễn Văn T5: 703561538; Lê Thị Mỹ H5: 703561538; "
            "Võ Văn P: 703561538"
        ),
    },
    "109": {
        "Expected_Articles": "611; 612; 613; 614; 649; 650; 651; 660",
        "Expected_Distribution": "Phạm Văn T: 1706300000; Phạm Văn N: 426575000",
    },
    "117": {
        "Expected_Articles": "611; 612; 613; 614; 640; 649; 650; 651; 652; 660",
        "Expected_Distribution": (
            "Thuỳ: 998172000; Mỵ: 998172000; T: 998172000; "
            "Cường: 425691000; Mạnh: 425691000; Thiên: 557802000"
        ),
    },
    "125": {
        "Expected_Articles": "612; 613; 624; 626; 643; 650; 651; 652; 660",
        "Expected_Distribution": (
            "Hoàng Thị D: 43418652; Hoàng Thị V: 43418652; "
            "Hoàng Thị Tr: 43418652; Hoàng Thị T: 43418652; "
            "Hoàng Lệ T1: 43418652; Nông Thị Thúy K: 21709326; "
            "Nông Thị Bích N: 21709326; Hoàng Thị H: 72364420; "
            "Hoàng Việt V1: 72364420"
        ),
    },
    "128": {
        "Expected_Articles": "609; 611; 612; 613; 614; 624; 626; 630; 643; 649; 650; 651; 659; 660",
    },
    "131": {
        "Expected_Distribution": (
            "H: 175551780; T: 87775890; N: 87775890; T1: 87775890; "
            "S: 87775890; T2: 87775890; N1: 21943973; H1: 21943973; "
            "B: 21943972; T3: 21943972"
        ),
    },
    "136": {
        "Expected_Distribution": (
            "T1: 17626719; T2: 17626719; C3: 17626718; Y: 17626718; "
            "T: 52880157; X: 17626719"
        ),
    },
    "140": {
        "Expected_Distribution": (
            "H3: 28955871; T4: 28955871; S1: 28955871; "
            "Phan Việt H: 28955871; H1: 43433808; X: 43433808"
        ),
    },
}


def replace_case_text(case_id: str, text: str) -> str:
    for old, new in REPLACEMENTS.get(case_id, []):
        normalized_new = new
        for pattern, replacement in NAME_STANDARDIZATIONS.get(case_id, []):
            normalized_new = re.sub(pattern, replacement, normalized_new)
        repeated = f"{normalized_new} {normalized_new}"
        while repeated in text:
            text = text.replace(repeated, normalized_new)
        if normalized_new.startswith(old):
            appended = normalized_new[len(old):].strip()
            duplicated_appendix = f"{normalized_new} {appended}"
            while appended and duplicated_appendix in text:
                text = text.replace(duplicated_appendix, normalized_new)
        if text.count(new) >= 1 or text.count(normalized_new) >= 1:
            continue
        count = text.count(old)
        if count != 1:
            raise ValueError(
                f"Case {case_id}: expected one occurrence, found {count}: {old!r}"
            )
        text = text.replace(old, new)
    for pattern, replacement in NAME_STANDARDIZATIONS.get(case_id, []):
        text = re.sub(pattern, replacement, text)
    return text


def main() -> None:
    with BENCHMARK_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0])

    found = {row["Case_ID"] for row in rows}
    missing = sorted(set(REPLACEMENTS) - found)
    if missing:
        raise ValueError(f"Missing benchmark cases: {missing}")

    for row in rows:
        row["User_Query"] = replace_case_text(row["Case_ID"], row["User_Query"])
        for field, value in REFERENCE_OVERRIDES.get(row["Case_ID"], {}).items():
            row[field] = value

    with BENCHMARK_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    legacy = json.loads(LEGACY_EXTRACTION_PATH.read_text(encoding="utf-8-sig"))
    by_id = {str(case["case_id"]): case for case in legacy}
    for row in rows:
        by_id[row["Case_ID"]]["query_text"] = row["User_Query"]
    LEGACY_EXTRACTION_PATH.write_text(
        json.dumps(legacy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Applied approved leakage-text repairs to {len(REPLACEMENTS)} cases.")


if __name__ == "__main__":
    main()
