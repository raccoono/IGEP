#!/usr/bin/env python3
"""Build the reviewed concept-level inheritance-law crosswalk.

The mapping is deliberately explicit. Article numbers are never inferred by
offset; every citation is listed against a legal concept after comparing the
article text in the normalized corpus.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/legal_corpus/normalized/statutes.jsonl"
OUTPUT = ROOT / "data/legal_corpus/crosswalk/crosswalk.csv"
DOCS = ("PLTK_1990", "BLDS_1995", "BLDS_2005", "BLDS_2015")


def c(doc: str, article: int) -> str:
    return f"VN_{doc}_ART_{article}"


# id, label, PLTK, 1995, 2005, 2015, relation, substantive comparison
ROWS = [
    ("inheritance_right", "Quyền thừa kế", [1], [634], [631], [609], "partially_changed", "Quyền lập di chúc và hưởng thừa kế được duy trì; BLDS 2015 diễn đạt thêm quyền hưởng theo di chúc hoặc pháp luật và quyền của người không phải cá nhân hưởng theo di chúc."),
    ("equality_in_inheritance", "Quyền bình đẳng về thừa kế", [2], [635], [632], [610], "equivalent", "Cùng bảo đảm bình đẳng trong quyền để lại và hưởng di sản; thay đổi chủ yếu về thuật ngữ."),
    ("opening_time_and_place", "Thời điểm và địa điểm mở thừa kế", [3], [636], [633], [611], "partially_changed", "Cùng lấy thời điểm chết và nơi cư trú cuối cùng; quy tắc người bị tuyên bố chết lần lượt dẫn chiếu Điều 91, 81 và 71; PLTK diễn đạt trực tiếp hơn."),
    ("estate_definition", "Di sản", [4], [637], [634], [612], "partially_changed", "Cùng bao gồm tài sản riêng và phần của người chết trong tài sản chung; cách mô tả phạm vi tài sản thay đổi qua các bản."),
    ("eligible_heir", "Người thừa kế", [5], [638], [635], [613], "partially_changed", "Cùng yêu cầu cá nhân còn sống hoặc thành thai trước khi mở thừa kế; các BLDS quy định rõ chủ thể không phải cá nhân tồn tại vào thời điểm mở thừa kế."),
    ("simultaneous_death", "Những người có quyền thừa kế của nhau chết cùng thời điểm", [6], [644], [641], [619], "partially_changed", "Nguyên tắc không thừa kế của nhau được duy trì; các BLDS nối rõ với thừa kế thế vị, còn PLTK quy định việc chia riêng di sản mỗi người."),
    ("rights_arise", "Thời điểm phát sinh quyền và nghĩa vụ của người thừa kế", [30], [639], [636], [614], "equivalent", "Quyền và nghĩa vụ phát sinh từ thời điểm mở thừa kế; khác biệt câu chữ không làm đổi quy tắc lõi."),
    ("estate_obligations", "Thực hiện nghĩa vụ tài sản do người chết để lại", [8, 32], [640], [637], [615], "partially_changed", "PLTK tách giới hạn nghĩa vụ và cách thực hiện ở hai điều; các BLDS hợp nhất, BLDS 2015 quy định rõ cả trường hợp di sản chưa và đã chia."),
    ("estate_manager", "Người quản lý di sản", [33], [641], [638], [616], "partially_changed", "PLTK chỉ quy định bảo quản; các BLDS xác định thứ tự/chủ thể quản lý và trường hợp chưa xác định được người thừa kế."),
    ("estate_manager_duties", "Nghĩa vụ của người quản lý di sản", [33], [642], [639], [617], "partially_changed", "Các BLDS chi tiết hóa nghĩa vụ lập danh mục, bảo quản, thông báo và bồi thường từ nền tảng bảo quản di sản của PLTK."),
    ("estate_manager_rights", "Quyền của người quản lý di sản", [], [643], [640], [618], "newly_added", "Không có điều độc lập tương ứng trong PLTK; BLDS quy định quyền đại diện, hưởng thù lao và chi phí bảo quản với một số điều chỉnh câu chữ."),
    ("refusal_of_estate", "Từ chối nhận di sản", [31], [645], [642], [620], "partially_changed", "PLTK còn cho phép nhường quyền và tính 6 tháng từ khi biết mở thừa kế; BLDS 1995/2005 dùng hạn 6 tháng từ khi mở; BLDS 2015 chỉ yêu cầu trước khi phân chia và đổi người nhận thông báo."),
    ("disqualified_heir", "Người không được quyền hưởng di sản", [7], [646], [643], [621], "partially_changed", "BLDS bổ sung xâm phạm danh dự, ngăn cản/sửa chữa di chúc; BLDS 2015 bổ sung che giấu di chúc. Ngoại lệ biết hành vi mà vẫn cho hưởng được duy trì."),
    ("unclaimed_estate", "Di sản không có người nhận thừa kế", [9], [647], [644], [622], "partially_changed", "Đều chuyển phần còn lại cho Nhà nước; BLDS 2015 nói rõ sau khi hoàn thành nghĩa vụ tài sản và dùng thuật ngữ tài sản còn lại."),
    ("inheritance_limitation", "Thời hiệu thừa kế", [36], [648], [645], [623], "partially_changed", "PLTK/BLDS 1995/2005 cơ bản dùng 10 năm cho yêu cầu về quyền/chia; BLDS 2015 tách 30 năm cho bất động sản, 10 năm cho động sản và quy định hệ quả hết hạn; nghĩa vụ tài sản là 3 năm."),
    ("will_definition", "Khái niệm di chúc", [], [649], [646], [624], "newly_added", "Không có điều định nghĩa độc lập trong PLTK; ba BLDS cùng xác định di chúc là ý chí chuyển tài sản sau khi chết, thay đổi chủ yếu về câu chữ."),
    ("testator_capacity", "Người lập di chúc", [10, 12], [650], [647], [625], "partially_changed", "PLTK phân tán tuổi/năng lực giữa quyền lập và tính hợp pháp; các BLDS gom tại điều người lập di chúc. Ngưỡng người chưa thành niên đổi từ đủ 16 xuống đủ 15 tuổi từ BLDS 1995."),
    ("testator_rights", "Quyền của người lập di chúc", [11], [651], [648], [626], "partially_changed", "Các quyền chỉ định, truất quyền, phân định phần, giao nghĩa vụ, dành phần thờ cúng và sửa/hủy được duy trì; các BLDS bổ sung quyền chỉ định người quản lý, phân chia di sản."),
    ("will_form", "Hình thức của di chúc", [13, 17, 18], [652], [649], [627], "partially_changed", "PLTK quy định hình thức rải ở nhiều điều; các BLDS có điều khung tách di chúc văn bản và miệng."),
    ("written_will_types", "Các loại di chúc bằng văn bản", [13, 14, 15, 16, 17], [653], [650], [628], "partially_changed", "Các BLDS hệ thống hóa bốn loại văn bản theo người làm chứng/công chứng/chứng thực; PLTK dùng cấu trúc chứng thực, giá trị tương đương và không chứng thực."),
    ("oral_will", "Di chúc miệng", [18], [654, 655], [651, 652], [629, 630], "partially_changed", "Điều kiện nguy cấp và mất hiệu lực sau khi người lập còn sống, minh mẫn được duy trì; thủ tục ghi chép/xác nhận được chi tiết hóa, BLDS 2015 tính 05 ngày làm việc."),
    ("lawful_will", "Điều kiện di chúc hợp pháp", [12], [655], [652], [630], "partially_changed", "Điều kiện tự nguyện, minh mẫn, nội dung và hình thức hợp pháp được duy trì nhưng tuổi, người hạn chế thể chất/không biết chữ và thủ tục di chúc miệng thay đổi đáng kể."),
    ("will_contents", "Nội dung của di chúc", [13], [656], [653], [631], "partially_changed", "Các thành phần cốt lõi được duy trì; BLDS 2015 cho phép nội dung khác, cấm viết tắt/ký hiệu và quy định đánh số, ký từng trang, tẩy xóa/sửa chữa."),
    ("will_witness", "Người làm chứng cho việc lập di chúc", [19], [657], [654], [632], "partially_changed", "Đều loại trừ người có lợi ích và người không đủ năng lực; PLTK đặt trong bối cảnh chứng thực/chứng kiến, các BLDS có quy tắc người làm chứng chung."),
    ("unwitnessed_written_will", "Di chúc bằng văn bản không có người làm chứng", [17], [658], [655], [633], "partially_changed", "PLTK chấp nhận nếu do chính người lập viết và ký; các BLDS dẫn thêm điều kiện nội dung và tính hợp pháp của di chúc."),
    ("witnessed_written_will", "Di chúc bằng văn bản có người làm chứng", [19], [659], [656], [634], "newly_added", "PLTK không có điều độc lập đầy đủ; các BLDS quy định ít nhất hai người làm chứng, ký/điểm chỉ và tuân thủ điều kiện nội dung/hình thức."),
    ("notarized_will", "Di chúc có công chứng hoặc chứng thực", [14], [660], [657], [635], "partially_changed", "Cùng thừa nhận di chúc được cơ quan có thẩm quyền xác nhận; tên cơ quan và khuôn khổ công chứng thay đổi theo thời kỳ."),
    ("notarized_will_procedure", "Thủ tục lập di chúc tại cơ quan công chứng hoặc UBND", [14], [661], [658], [636], "partially_changed", "Các BLDS chi tiết hóa việc tuyên bố nội dung, ghi chép, ký/điểm chỉ và chứng nhận; BLDS 2015 dùng tổ chức hành nghề công chứng và UBND cấp xã."),
    ("barred_notary_or_certifier", "Người không được công chứng hoặc chứng thực di chúc", [19], [662], [659], [637], "partially_changed", "Đều loại trừ người thừa kế/người có lợi ích và người thân thích; phạm vi, thuật ngữ năng lực hành vi và chủ thể chứng nhận thay đổi."),
    ("equivalent_to_notarized_will", "Di chúc văn bản có giá trị như được công chứng hoặc chứng thực", [15, 16], [663], [660], [638], "partially_changed", "Cùng công nhận các văn bản đặc thù như quân nhân, người trên tàu/phi cơ, cơ sở chữa bệnh, khảo sát và công dân ở nước ngoài; danh mục/chức danh có điều chỉnh."),
    ("notary_at_residence", "Di chúc do công chứng viên lập tại chỗ ở", [14], [664], [661], [639], "partially_changed", "Không có điều độc lập trong PLTK; ba BLDS cho phép yêu cầu lập tại chỗ ở và áp dụng thủ tục tương ứng."),
    ("will_amend_replace_revoke", "Sửa đổi, bổ sung, thay thế hoặc hủy bỏ di chúc", [22], [665], [662], [640], "partially_changed", "Quyền thay đổi được duy trì; các BLDS xử lý xung đột giữa các bản/phần di chúc và việc bổ sung."),
    ("joint_spousal_will", "Di chúc chung của vợ chồng", [], [666], [663], [], "repealed", "Được quy định thành điều riêng trong BLDS 1995 và 2005; BLDS 2015 không duy trì chế định điều riêng này."),
    ("joint_will_amendment", "Sửa đổi, bổ sung, thay thế hoặc hủy bỏ di chúc chung", [], [667], [664], [], "repealed", "Quy tắc đồng thuận và quyền sửa phần của mình khi bên kia chết từng có trong BLDS 1995/2005; không còn điều tương ứng trong BLDS 2015."),
    ("will_deposit", "Gửi giữ di chúc", [], [668], [665], [641], "partially_changed", "Được bổ sung từ BLDS 1995; BLDS 2015 tiếp tục nhưng cập nhật chủ thể nhận giữ và nghĩa vụ bảo quản/công bố."),
    ("lost_or_damaged_will", "Di chúc bị thất lạc hoặc hư hại", [], [669], [666], [642], "partially_changed", "Được bổ sung từ BLDS 1995; BLDS 2015 bổ sung xử lý khi tìm thấy di chúc trong thời hiệu yêu cầu chia di sản."),
    ("will_effect", "Hiệu lực của di chúc", [23], [670], [667], [643], "partially_changed", "Cùng có hiệu lực từ mở thừa kế và vô hiệu khi người thừa kế/chủ thể không còn hoặc di sản không còn; các BLDS chi tiết hóa vô hiệu từng phần và nhiều bản di chúc."),
    ("joint_will_effect", "Hiệu lực của di chúc chung vợ chồng", [], [671], [668], [], "repealed", "BLDS 1995/2005 quy định thời điểm hiệu lực riêng cho di chúc chung; BLDS 2015 bỏ điều riêng cùng với chế định di chúc chung."),
    ("compulsory_heir", "Người thừa kế không phụ thuộc nội dung di chúc", [20], [672], [669], [644], "partially_changed", "Mức hai phần ba suất được duy trì; PLTK đòi cha/mẹ/vợ/chồng/con thành niên không có khả năng lao động còn túng thiếu, điều kiện túng thiếu bị bỏ từ BLDS 1995."),
    ("worship_estate", "Di sản dùng vào việc thờ cúng", [21], [673], [670], [645], "partially_changed", "Việc dành phần di sản thờ cúng và chỉ định người quản lý được duy trì; các BLDS chi tiết hóa trường hợp không thực hiện đúng và nghĩa vụ tài sản chưa đủ."),
    ("legacy_gift", "Di tặng", [], [674], [671], [646], "newly_added", "Không có điều độc lập trong PLTK; từ BLDS 1995 quy định di tặng, trách nhiệm nghĩa vụ tài sản và ngoại lệ cho tổ chức."),
    ("will_publication", "Công bố di chúc", [], [675], [672], [647], "partially_changed", "Không có điều độc lập trong PLTK; các BLDS quy định người công bố, sao gửi và đối chiếu bản gốc, với điều chỉnh theo việc gửi giữ."),
    ("will_interpretation", "Giải thích nội dung di chúc", [], [676], [673], [648], "partially_changed", "Từ BLDS 1995 ưu tiên ý nguyện đích thực và thỏa thuận của người thừa kế; BLDS 2015 bỏ phương án coi như không có di chúc khi không thỏa thuận được và nhấn mạnh ý nguyện/nghĩa lý."),
    ("intestate_definition", "Khái niệm thừa kế theo pháp luật", [], [677], [674], [649], "newly_added", "Không có điều định nghĩa độc lập trong PLTK; ba BLDS định nghĩa theo hàng, điều kiện và trình tự do pháp luật quy định."),
    ("intestate_cases", "Những trường hợp thừa kế theo pháp luật", [24], [678], [675], [650], "partially_changed", "Nhóm không có/không hợp pháp/không còn người hưởng di chúc và phần không được định đoạt được duy trì; cách liệt kê và dẫn chiếu thay đổi."),
    ("statutory_heir_orders", "Hàng thừa kế theo pháp luật", [25], [679], [676], [651], "partially_changed", "Ba hàng và nguyên tắc cùng hàng bằng nhau được duy trì; BLDS 2005/2015 bổ sung cháu vào hàng hai và chắt vào hàng ba so với PLTK/BLDS 1995."),
    ("representation", "Thừa kế thế vị", [26], [680], [677], [652], "partially_changed", "PLTK/BLDS 1995 chỉ nói chết trước; BLDS 2005/2015 mở rộng cho con hoặc cháu chết cùng thời điểm với người để lại di sản."),
    ("adoptive_inheritance", "Thừa kế giữa con nuôi, cha mẹ nuôi và cha mẹ đẻ", [27], [681], [678], [653], "equivalent", "Quyền thừa kế giữa con nuôi với cả cha mẹ nuôi và cha mẹ đẻ, đồng thời áp dụng thế vị, được duy trì."),
    ("stepfamily_inheritance", "Thừa kế giữa con riêng và bố dượng, mẹ kế", [28], [682], [679], [654], "equivalent", "Điều kiện có quan hệ chăm sóc, nuôi dưỡng nhau như cha con/mẹ con và quyền thừa kế hai chiều được duy trì."),
    ("spousal_status_inheritance", "Thừa kế khi vợ chồng chia tài sản, đang ly hôn hoặc tái hôn", [29], [683], [680], [655], "partially_changed", "Quyền của vợ/chồng còn sống cơ bản được duy trì; các BLDS diễn đạt rõ trường hợp bản án ly hôn chưa có hiệu lực và người sống kết hôn lại."),
    ("heirs_meeting", "Họp mặt những người thừa kế", [], [684], [681], [656], "newly_added", "Không có điều độc lập trong PLTK; từ BLDS 1995 quy định thỏa thuận về quản lý, phân chia và hình thức văn bản."),
    ("estate_distributor", "Người phân chia di sản", [35], [685], [682], [657], "partially_changed", "PLTK tập trung vào phân chia; các BLDS xác định người được chỉ định hoặc được thỏa thuận và quyền hưởng thù lao."),
    ("payment_priority", "Thứ tự ưu tiên thanh toán từ di sản", [34], [686], [683], [658], "partially_changed", "PLTK có 8 nhóm khoản chi; BLDS 1995/2005 có 10 nhóm, BLDS 2015 điều chỉnh thứ tự và tên gọi, gồm chi phí bảo quản và nghĩa vụ với Nhà nước."),
    ("distribution_by_will", "Phân chia di sản theo di chúc", [35], [687], [684], [659], "partially_changed", "Nguyên tắc theo ý chí người lập được duy trì; các BLDS quy định cách hiểu theo tỷ lệ, hiện vật và hoa lợi/lợi tức."),
    ("distribution_by_law", "Phân chia di sản theo pháp luật", [35], [688], [685], [660], "partially_changed", "Các BLDS chi tiết hóa việc dành phần cho người đã thành thai nhưng chưa sinh và phương thức chia hiện vật/giá trị; PLTK quy định khái quát."),
    ("distribution_restriction", "Hạn chế phân chia di sản", [], [689], [686], [661], "partially_changed", "Được bổ sung từ BLDS 1995; BLDS 2015 bổ sung quyền yêu cầu Tòa án gia hạn một lần, tối đa 03 năm, khi chia di sản ảnh hưởng nghiêm trọng đời sống."),
    ("new_or_rejected_heir", "Phân chia khi có người thừa kế mới hoặc bị bác bỏ quyền", [], [], [687], [662], "newly_added", "Xuất hiện từ BLDS 2005 và được duy trì gần như tương đương trong BLDS 2015; ưu tiên thanh toán giá trị thay vì chia lại bằng hiện vật."),
    ("foreign_national_inheritance", "Quyền thừa kế của người nước ngoài", [37], [], [], [], "no_standalone_equivalent", "PLTK có điều riêng; các BLDS không đặt điều độc lập trong chương thừa kế, vấn đề được điều chỉnh bởi các quy định chung và tư pháp quốc tế."),
    ("repeal_of_prior_rules", "Bãi bỏ quy định thừa kế trước đây trái văn bản", [38], [], [], [], "no_standalone_equivalent", "Đây là quy phạm bãi bỏ của PLTK, không phải chế định thừa kế nội dung và không có điều tương ứng trong các chương thừa kế BLDS."),
]


def main() -> None:
    records = [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines() if line]
    known = {record["citation_id"] for record in records}
    fields = [
        "concept_id", "concept_label_vi", *[f"{doc}_citation_ids" for doc in DOCS],
        "relation", "comparison_notes", "mapping_basis", "review_status",
    ]
    output_rows = []
    used: set[str] = set()
    for concept_id, label, *rest in ROWS:
        article_lists, relation, notes = rest[:4], rest[4], rest[5]
        row = {"concept_id": concept_id, "concept_label_vi": label}
        for doc, articles in zip(DOCS, article_lists):
            citations = [c(doc, article) for article in articles]
            missing = set(citations) - known
            if missing:
                raise ValueError(f"Unknown citations for {concept_id}: {sorted(missing)}")
            used.update(citations)
            row[f"{doc}_citation_ids"] = ";".join(citations)
        row.update(
            relation=relation,
            comparison_notes=notes,
            mapping_basis="manual_substantive_text_comparison",
            review_status="machine_checked_pending_legal_expert_review",
        )
        output_rows.append(row)

    relevant = {r["citation_id"] for r in records if r["inheritance_relevant"]}
    uncovered = relevant - used
    if uncovered:
        raise ValueError(f"Inheritance citations not covered: {sorted(uncovered)}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"Wrote {len(output_rows)} concepts covering {len(used)} citations to {OUTPUT}")


if __name__ == "__main__":
    main()
