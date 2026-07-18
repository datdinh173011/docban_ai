import { Locale } from "./i18n";

export type PrivacyBlock = { text: string } | { items: string[] };
export type PrivacySection = { heading: string; blocks: PrivacyBlock[] };

function p(text: string): PrivacyBlock {
  return { text };
}
function ul(items: string[]): PrivacyBlock {
  return { items };
}

export const privacyIntro: Record<Locale, string[]> = {
  vi: [
    "Điều khoản sử dụng này quy định việc truy cập và sử dụng nền tảng CIVI — công cụ ứng dụng trí tuệ nhân tạo hỗ trợ người dân tìm hiểu, chuẩn bị và kiểm tra trước hồ sơ thủ tục hành chính.",
    "Bằng việc truy cập hoặc sử dụng hệ thống, người dùng xác nhận đã đọc, hiểu và đồng ý với các điều khoản dưới đây.",
  ],
  en: [
    "These Terms of Use govern access to and use of the CIVI platform — an AI-powered tool that helps citizens research, prepare, and pre-check administrative procedure applications.",
    "By accessing or using the system, users confirm that they have read, understood, and agreed to the terms below.",
  ],
  mww: [
    "Cov Cai Siv no teev txog kev nkag mus thiab siv lub platform CIVI — ib lub cuab yeej AI pab cov pej xeem kawm txog, npaj, thiab kuaj daim ntawv thov ua ntej xa mus rau txheej txheem nom tswv.",
    "Los ntawm kev nkag mus los sis siv lub kaw lus no, tus neeg siv lees paub tias twb nyeem, nkag siab, thiab pom zoo raws li cov cai hauv qab no.",
  ],
  km: [
    "លក្ខខណ្ឌប្រើប្រាស់នេះកំណត់អំពីការចូលប្រើ និងការប្រើប្រាស់វេទិកា CIVI — ឧបករណ៍ដែលប្រើបញ្ញាសិប្បនិមិត្តជួយប្រជាពលរដ្ឋស្វែងយល់ រៀបចំ និងពិនិត្យជាមុននូវឯកសារនីតិវិធីរដ្ឋបាល។",
    "ដោយការចូលប្រើ ឬប្រើប្រាស់ប្រព័ន្ធនេះ អ្នកប្រើប្រាស់បញ្ជាក់ថាបានអាន យល់ និងយល់ព្រមតាមលក្ខខណ្ឌខាងក្រោម។",
  ],
};

export const privacyContent: Record<Locale, PrivacySection[]> = {
  vi: [
    {
      heading: "Điều 1. Thông tin về hệ thống",
      blocks: [
        p("CIVI là sản phẩm xây dựng nhằm hỗ trợ người dùng:"),
        ul([
          "Xác định thủ tục hành chính phù hợp với nhu cầu;",
          "Tra cứu thành phần hồ sơ, biểu mẫu và cơ quan thực hiện;",
          "Nhận hướng dẫn từng bước;",
          "Kiểm tra sơ bộ thông tin trước khi nộp hồ sơ;",
          "Phát hiện các trường còn thiếu, lỗi định dạng hoặc thông tin có dấu hiệu không thống nhất.",
        ]),
      ],
    },
    {
      heading: "Điều 2. Phạm vi hỗ trợ của AI",
      blocks: [
        p("AI có thể hỗ trợ người dùng:"),
        ul([
          "Làm rõ nhu cầu thực hiện thủ tục;",
          "Đề xuất thủ tục phù hợp dựa trên thông tin được cung cấp;",
          "Liệt kê giấy tờ, biểu mẫu và các bước cần thực hiện;",
          "Minh họa cách điền một số trường thông tin;",
          "Kiểm tra sơ bộ tính đầy đủ và nhất quán của dữ liệu;",
          "Dẫn nguồn để người dùng kiểm tra thông tin.",
        ]),
        p("Kết quả do AI tạo ra chỉ mang tính chất hỗ trợ và tham khảo."),
        p("AI không có thẩm quyền:"),
        ul([
          "Chứng nhận thông tin do người dùng cung cấp;",
          "Cấp giấy phép, giấy chứng nhận hoặc kết quả thủ tục;",
          "Thay mặt cơ quan nhà nước giải quyết thủ tục hành chính.",
        ]),
        p("Kết quả kiểm tra trước không đồng nghĩa với việc hồ sơ chắc chắn được cơ quan có thẩm quyền tiếp nhận hoặc phê duyệt."),
      ],
    },
    {
      heading: "Điều 3. Điều kiện sử dụng",
      blocks: [
        p("Người dùng phải có năng lực hành vi phù hợp theo quy định pháp luật để sử dụng hệ thống."),
        p("Trường hợp người dùng chưa thành niên hoặc bị hạn chế về năng lực hành vi, việc sử dụng hệ thống cần được thực hiện với sự hướng dẫn hoặc đồng ý của người đại diện hợp pháp, khi pháp luật yêu cầu."),
        p("Người dùng tự chịu trách nhiệm về thiết bị, kết nối Internet và khả năng truy cập hệ thống."),
        p("Hệ thống có thể cung cấp chế độ sử dụng không cần tài khoản. Nếu có chức năng đăng ký tài khoản, người dùng phải cung cấp thông tin chính xác và bảo vệ thông tin đăng nhập của mình."),
      ],
    },
    {
      heading: "Điều 4. Trách nhiệm của người dùng",
      blocks: [
        p("Khi sử dụng hệ thống, người dùng có trách nhiệm:"),
        ul([
          "Cung cấp thông tin trung thực, chính xác và cần thiết cho mục đích kiểm tra hồ sơ.",
          "Tự kiểm tra lại kết quả do AI cung cấp trước khi sử dụng để thực hiện thủ tục.",
          "Không sử dụng kết quả của hệ thống để giả mạo hồ sơ, khai báo gian dối hoặc thực hiện hành vi trái pháp luật.",
          "Chỉ cung cấp dữ liệu cá nhân của người khác khi có căn cứ hợp pháp và đã thực hiện đầy đủ nghĩa vụ thông báo, xin sự đồng ý hoặc nghĩa vụ khác theo quy định.",
        ]),
      ],
    },
    {
      heading: "Điều 5. Các hành vi bị cấm",
      blocks: [
        p("Người dùng không được:"),
        ul([
          "Sử dụng hệ thống để thực hiện hành vi vi phạm pháp luật.",
          "Cung cấp thông tin giả mạo, xuyên tạc hoặc cố ý gây nhầm lẫn.",
          "Mạo danh cá nhân, tổ chức hoặc cơ quan nhà nước.",
          "Tải lên mã độc, phần mềm gây hại hoặc nội dung có khả năng ảnh hưởng đến hoạt động của hệ thống.",
          "Tấn công, dò quét lỗ hổng, can thiệp trái phép hoặc tìm cách vượt qua biện pháp bảo mật.",
          "Thu thập dữ liệu hàng loạt, sao chép tự động hoặc khai thác hệ thống bằng bot khi chưa được phép.",
          "Sử dụng kết quả AI để lừa đảo, làm giả giấy tờ hoặc xâm phạm quyền và lợi ích hợp pháp của người khác.",
          "Sao chép, sửa đổi, phân phối hoặc khai thác thương mại mã nguồn, giao diện, cơ sở dữ liệu hoặc nội dung thuộc quyền sở hữu của đơn vị vận hành, trừ trường hợp được phép bằng văn bản.",
        ]),
      ],
    },
    {
      heading: "Điều 6. Dữ liệu do người dùng cung cấp",
      blocks: [
        p("Hệ thống chỉ nên thu thập dữ liệu cần thiết để:"),
        ul([
          "Hiểu yêu cầu của người dùng;",
          "Đưa ra hướng dẫn thủ tục;",
          "Kiểm tra thông tin;",
          "Phát hiện lỗi kỹ thuật;",
          "Cải thiện chất lượng hệ thống trong phạm vi được phép.",
        ]),
        p("Việc thu thập, lưu trữ, sử dụng, chia sẻ và xóa dữ liệu được thực hiện theo Chính sách bảo vệ dữ liệu cá nhân của hệ thống."),
        p("Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 có hiệu lực từ ngày 1/1/2026 và là căn cứ pháp lý quan trọng đối với hoạt động xử lý dữ liệu cá nhân tại Việt Nam."),
      ],
    },
    {
      heading: "Điều 7. Nguồn dữ liệu thủ tục hành chính",
      blocks: [
        p("Hệ thống sử dụng hoặc tham khảo dữ liệu công khai từ các nguồn như:"),
        ul([
          "Cổng Dịch vụ công Quốc gia;",
          "Cơ sở dữ liệu quốc gia về thủ tục hành chính;",
          "Cổng thông tin của bộ, ngành và địa phương;",
          "Văn bản pháp luật;",
          "Biểu mẫu hành chính do cơ quan có thẩm quyền công bố.",
        ]),
        p("Đơn vị vận hành cố gắng cập nhật dữ liệu thường xuyên nhưng không cam kết rằng mọi thông tin luôn đầy đủ hoặc mới nhất tại mọi thời điểm."),
        p("Mỗi hướng dẫn nên hiển thị, khi có thể:"),
        ul(["Nguồn dữ liệu;", "Ngày cập nhật;", "Cơ quan công bố;", "Căn cứ pháp lý;", "Đường dẫn để kiểm chứng."]),
        p("Trường hợp có khác biệt giữa kết quả AI và thông tin chính thức, thông tin do cơ quan có thẩm quyền công bố được ưu tiên áp dụng."),
      ],
    },
    {
      heading: "Điều 8. Giới hạn của kết quả AI",
      blocks: [
        p("Người dùng hiểu và chấp nhận rằng:"),
        ul(["AI có thể trả lời sai, thiếu hoặc chưa cập nhật.", "AI có thể hiểu chưa đúng tình huống do người dùng mô tả chưa đầy đủ."]),
        p("Yêu cầu thủ tục có thể khác nhau tùy:"),
        ul([
          "Địa phương;",
          "Thời điểm nộp hồ sơ;",
          "Tình trạng pháp lý của người yêu cầu;",
          "Loại tài sản hoặc đối tượng;",
          "Quy định chuyển tiếp;",
          "Trường hợp đặc thù.",
        ]),
        p("Chức năng kiểm tra trước chỉ có thể phát hiện một số dạng lỗi, ví dụ:"),
        ul(["Trường còn trống;", "Sai định dạng;", "Ngày tháng không hợp lệ;", "Dữ liệu có dấu hiệu mâu thuẫn;", "Thiếu tài liệu theo danh mục đã biết."]),
        p("Hệ thống không thể xác định chắc chắn:"),
        ul([
          "Giấy tờ có thật hay giả;",
          "Chữ ký có hợp lệ hay không;",
          "Người khai có đủ thẩm quyền hay không;",
          "Hồ sơ có đáp ứng toàn bộ yêu cầu thực tế của cơ quan tiếp nhận hay không.",
        ]),
      ],
    },
    {
      heading: "Điều 9. Miễn trừ và giới hạn trách nhiệm",
      blocks: [
        p("Đơn vị vận hành không bảo đảm rằng hệ thống sẽ hoạt động liên tục, không có lỗi hoặc đáp ứng mọi nhu cầu của người dùng."),
        p("Trong phạm vi pháp luật cho phép, đơn vị vận hành không chịu trách nhiệm đối với thiệt hại phát sinh trực tiếp từ việc người dùng:"),
        ul([
          "Cung cấp thông tin không chính xác;",
          "Không kiểm tra lại kết quả;",
          "Không đối chiếu với nguồn chính thức;",
          "Sử dụng AI ngoài phạm vi hỗ trợ;",
          "Nhập dữ liệu nhạy cảm trái với cảnh báo;",
          "Sử dụng kết quả để thực hiện hành vi trái pháp luật.",
        ]),
        p("Điều khoản này không loại trừ trách nhiệm mà pháp luật không cho phép miễn trừ, bao gồm trách nhiệm phát sinh từ hành vi cố ý vi phạm, gian dối hoặc vi phạm nghĩa vụ bảo vệ quyền lợi hợp pháp của người dùng."),
        p("Nếu hệ thống được cung cấp cho người tiêu dùng, việc xây dựng và áp dụng điều khoản phải phù hợp với Luật Bảo vệ quyền lợi người tiêu dùng năm 2023, có hiệu lực từ ngày 1/7/2024."),
      ],
    },
    {
      heading: "Điều 10. Quyền sở hữu trí tuệ",
      blocks: [
        p("Tên, logo, giao diện, mã nguồn, thiết kế, tài liệu kỹ thuật và nội dung do Nhóm Độc Bản tự phát triển thuộc quyền sở hữu của đơn vị này hoặc bên cấp phép tương ứng."),
        p("Văn bản pháp luật, biểu mẫu và dữ liệu hành chính được sử dụng theo chế độ pháp lý áp dụng đối với từng nguồn."),
        p("Người dùng được phép sử dụng kết quả AI cho mục đích cá nhân và thực hiện thủ tục hợp pháp."),
        p("Người dùng không được tuyên bố kết quả AI là thông tin chính thức do cơ quan nhà nước ban hành."),
      ],
    },
    {
      heading: "Điều 11. Tạm ngừng hoặc chấm dứt quyền sử dụng",
      blocks: [
        p("Đơn vị vận hành có quyền tạm ngừng hoặc chấm dứt quyền truy cập khi người dùng:"),
        ul([
          "Vi phạm điều khoản này;",
          "Có hành vi tấn công hoặc gây nguy hiểm cho hệ thống;",
          "Sử dụng hệ thống để gian lận;",
          "Xâm phạm quyền của người khác;",
          "Làm ảnh hưởng đến hoạt động của người dùng khác.",
        ]),
        p("Trong trường hợp khẩn cấp về an ninh, an toàn hệ thống, việc tạm ngừng có thể được thực hiện ngay."),
      ],
    },
    {
      heading: "Điều 12. Thay đổi và bảo trì hệ thống",
      blocks: [
        p("Đơn vị vận hành có thể sửa đổi, bổ sung hoặc ngừng một phần chức năng để:"),
        ul(["Bảo trì;", "Sửa lỗi;", "Nâng cấp mô hình AI;", "Cập nhật dữ liệu;", "Tuân thủ yêu cầu pháp luật;", "Bảo đảm an toàn hệ thống."]),
        p("Đối với thay đổi quan trọng ảnh hưởng đến quyền của người dùng, hệ thống nên thông báo trước bằng phương thức phù hợp."),
        p("Ngày cập nhật điều khoản phải được hiển thị rõ ở đầu trang."),
      ],
    },
    {
      heading: "Điều 13. Luật áp dụng và giải quyết tranh chấp",
      blocks: [
        p("Điều khoản này được điều chỉnh bởi pháp luật Việt Nam."),
        p("Tranh chấp trước hết được giải quyết thông qua thương lượng và trao đổi thiện chí."),
        p("Nếu không thể giải quyết bằng thương lượng, tranh chấp được giải quyết tại cơ quan có thẩm quyền theo pháp luật Việt Nam."),
        p("Điều khoản này không hạn chế quyền khiếu nại, tố cáo, yêu cầu bảo vệ dữ liệu cá nhân hoặc quyền khởi kiện hợp pháp của người dùng."),
      ],
    },
    {
      heading: "Điều 17. Hiệu lực từng phần",
      blocks: [
        p("Nếu một điều khoản bị xác định là vô hiệu hoặc không thể thi hành, các điều khoản còn lại vẫn tiếp tục có hiệu lực trong phạm vi pháp luật cho phép."),
      ],
    },
    {
      heading: "Điều 18. Thông tin đơn vị vận hành",
      blocks: [
        ul([
          "Tên dự án: CIVI",
          "Đơn vị phát triển: Nhóm Độc Bản",
          "Người đại diện/phụ trách: Nguyễn Thị Chi Ninh",
          "Email: ninh2023nguyen@gmail.com",
          "Tình trạng: Bản demo thử nghiệm",
        ]),
      ],
    },
  ],
  en: [
    {
      heading: "Article 1. About the system",
      blocks: [
        p("CIVI is built to help users:"),
        ul([
          "Identify the administrative procedure that matches their need;",
          "Look up required documents, forms, and the responsible authority;",
          "Receive step-by-step guidance;",
          "Pre-check information before submitting an application;",
          "Detect missing fields, formatting errors, or inconsistent information.",
        ]),
      ],
    },
    {
      heading: "Article 2. Scope of AI support",
      blocks: [
        p("The AI can help users:"),
        ul([
          "Clarify the procedure they need;",
          "Suggest a suitable procedure based on the information provided;",
          "List the documents, forms, and steps required;",
          "Illustrate how to fill in certain fields;",
          "Pre-check the completeness and consistency of data;",
          "Cite sources so users can verify information.",
        ]),
        p("Results generated by the AI are for support and reference purposes only."),
        p("The AI does not have the authority to:"),
        ul([
          "Certify information provided by the user;",
          "Issue licenses, certificates, or procedure outcomes;",
          "Act on behalf of a state authority to process an administrative procedure.",
        ]),
        p("A pre-check result does not guarantee that an application will be accepted or approved by the competent authority."),
      ],
    },
    {
      heading: "Article 3. Conditions of use",
      blocks: [
        p("Users must have the legal capacity required by law to use the system."),
        p("Where a user is a minor or has limited legal capacity, use of the system must be carried out with the guidance or consent of a legal representative, where required by law."),
        p("Users are responsible for their own device, Internet connection, and ability to access the system."),
        p("The system may offer a mode of use that does not require an account. Where account registration is available, users must provide accurate information and protect their login credentials."),
      ],
    },
    {
      heading: "Article 4. User responsibilities",
      blocks: [
        p("When using the system, users are responsible for:"),
        ul([
          "Providing truthful, accurate information necessary for reviewing the application.",
          "Verifying the AI's results themselves before using them to carry out a procedure.",
          "Not using the system's results to forge documents, make false declarations, or engage in unlawful conduct.",
          "Only providing another person's personal data where there is a lawful basis and after fulfilling all applicable notice, consent, or other legal obligations.",
        ]),
      ],
    },
    {
      heading: "Article 5. Prohibited conduct",
      blocks: [
        p("Users must not:"),
        ul([
          "Use the system to engage in unlawful conduct.",
          "Provide false, misleading, or intentionally confusing information.",
          "Impersonate an individual, organization, or state authority.",
          "Upload malicious code, harmful software, or content that could affect the system's operation.",
          "Attack, scan for vulnerabilities, interfere without authorization, or attempt to bypass security measures.",
          "Bulk-harvest data, automatically scrape, or exploit the system with bots without authorization.",
          "Use AI results to commit fraud, forge documents, or infringe the rights and lawful interests of others.",
          "Copy, modify, distribute, or commercially exploit the source code, interface, database, or content owned by the operator, except where permitted in writing.",
        ]),
      ],
    },
    {
      heading: "Article 6. Data provided by users",
      blocks: [
        p("The system should only collect data necessary to:"),
        ul([
          "Understand the user's request;",
          "Provide procedure guidance;",
          "Check information;",
          "Detect technical errors;",
          "Improve system quality within permitted limits.",
        ]),
        p("The collection, storage, use, sharing, and deletion of data is carried out in accordance with the system's Personal Data Protection Policy."),
        p("Personal Data Protection Law No. 91/2025/QH15, effective from 1 January 2026, is an important legal basis for personal data processing activities in Vietnam."),
      ],
    },
    {
      heading: "Article 7. Sources of administrative procedure data",
      blocks: [
        p("The system uses or references public data from sources such as:"),
        ul([
          "The National Public Service Portal;",
          "The national database on administrative procedures;",
          "Portals of ministries, sectors, and localities;",
          "Legal documents;",
          "Administrative forms published by competent authorities.",
        ]),
        p("The operator makes reasonable efforts to keep data up to date but does not guarantee that all information is always complete or current at every point in time."),
        p("Where possible, each piece of guidance should display:"),
        ul(["The data source;", "The update date;", "The publishing authority;", "The legal basis;", "A link for verification."]),
        p("Where there is a discrepancy between an AI result and official information, information published by the competent authority takes precedence."),
      ],
    },
    {
      heading: "Article 8. Limitations of AI results",
      blocks: [
        p("Users understand and accept that:"),
        ul(["The AI may give answers that are incorrect, incomplete, or outdated.", "The AI may misunderstand a situation if the user's description is incomplete."]),
        p("Procedure requirements may vary depending on:"),
        ul([
          "Locality;",
          "The time the application is submitted;",
          "The applicant's legal status;",
          "The type of asset or subject matter;",
          "Transitional regulations;",
          "Special or unusual cases.",
        ]),
        p("The pre-check feature can only detect certain types of errors, for example:"),
        ul(["Empty fields;", "Incorrect formatting;", "Invalid dates;", "Data that appears inconsistent;", "Missing documents from a known checklist."]),
        p("The system cannot definitively determine:"),
        ul([
          "Whether a document is genuine or forged;",
          "Whether a signature is valid;",
          "Whether the declarant has sufficient authority;",
          "Whether the application meets all of the receiving authority's actual requirements.",
        ]),
      ],
    },
    {
      heading: "Article 9. Disclaimers and limitation of liability",
      blocks: [
        p("The operator does not guarantee that the system will operate continuously, be error-free, or meet every user's needs."),
        p("To the extent permitted by law, the operator is not liable for damage arising directly from a user:"),
        ul([
          "Providing inaccurate information;",
          "Failing to verify the results;",
          "Failing to cross-check against official sources;",
          "Using the AI outside its intended scope of support;",
          "Entering sensitive data contrary to a displayed warning;",
          "Using the results to engage in unlawful conduct.",
        ]),
        p("This clause does not exclude liability that the law does not permit to be excluded, including liability arising from intentional violations, fraud, or breach of the obligation to protect users' lawful rights and interests."),
        p("Where the system is provided to consumers, these terms must be drafted and applied in accordance with the 2023 Law on Protection of Consumers' Rights, effective from 1 July 2024."),
      ],
    },
    {
      heading: "Article 10. Intellectual property",
      blocks: [
        p("The name, logo, interface, source code, design, technical documentation, and content developed by Nhóm Độc Bản belong to that organization or its respective licensors."),
        p("Legal documents, forms, and administrative data are used under the legal regime applicable to each source."),
        p("Users may use AI results for personal purposes and for carrying out lawful procedures."),
        p("Users must not represent AI results as official information issued by a state authority."),
      ],
    },
    {
      heading: "Article 11. Suspension or termination of access",
      blocks: [
        p("The operator may suspend or terminate a user's access where the user:"),
        ul([
          "Violates these terms;",
          "Attacks or endangers the system;",
          "Uses the system to commit fraud;",
          "Infringes the rights of others;",
          "Affects the operation of the system for other users.",
        ]),
        p("In an emergency involving security or system safety, suspension may take effect immediately."),
      ],
    },
    {
      heading: "Article 12. Changes and system maintenance",
      blocks: [
        p("The operator may modify, add to, or discontinue part of the system's functionality in order to:"),
        ul(["Perform maintenance;", "Fix bugs;", "Upgrade the AI model;", "Update data;", "Comply with legal requirements;", "Ensure system safety."]),
        p("For significant changes affecting users' rights, the system should give advance notice through an appropriate method."),
        p("The date these terms were last updated must be clearly displayed at the top of the page."),
      ],
    },
    {
      heading: "Article 13. Governing law and dispute resolution",
      blocks: [
        p("These terms are governed by the laws of Vietnam."),
        p("Disputes shall first be resolved through good-faith negotiation."),
        p("Where negotiation fails, disputes shall be resolved by the competent authority in accordance with the laws of Vietnam."),
        p("These terms do not limit a user's right to complain, report, request personal data protection, or bring a lawful lawsuit."),
      ],
    },
    {
      heading: "Article 17. Severability",
      blocks: [
        p("If any provision is found to be invalid or unenforceable, the remaining provisions shall continue in effect to the extent permitted by law."),
      ],
    },
    {
      heading: "Article 18. Operator information",
      blocks: [
        ul([
          "Project name: CIVI",
          "Developed by: Nhóm Độc Bản",
          "Representative/contact person: Nguyễn Thị Chi Ninh",
          "Email: ninh2023nguyen@gmail.com",
          "Status: Trial demo",
        ]),
      ],
    },
  ],
  mww: [
    {
      heading: "Nqe 1. Txog lub kaw lus",
      blocks: [
        p("CIVI yog tsim los pab cov neeg siv:"),
        ul([
          "Nrhiav txheej txheem nom tswv uas raug rau qhov xav tau;",
          "Tshawb cov ntawv, daim foos thiab lub chaw ua haujlwm uas ua;",
          "Tau txais lus qhia txhua kauj ruam;",
          "Kuaj ua ntej xa daim ntawv thov;",
          "Nrhiav cov chaw seem, sau tsis raug hom lossis lus tsis sib xws.",
        ]),
      ],
    },
    {
      heading: "Nqe 2. Qhov AI pab tau",
      blocks: [
        p("AI pab tau cov neeg siv:"),
        ul([
          "Ua kom meej txog qhov xav ua;",
          "Qhia txheej txheem tsim nyog raws li cov ntaub ntawv muab;",
          "Teev cov ntawv, daim foos thiab kauj ruam yuav tsum ua;",
          "Qhia yam sau qee cov chaw;",
          "Kuaj seb cov ntaub ntawv puv npo thiab sib xws;",
          "Qhia qhov chaw los kom neeg siv mus xyuas.",
        ]),
        p("Qhov AI muab tsuas yog pab thiab siv saib xwb."),
        p("AI tsis muaj cai:"),
        ul([
          "Lees paub cov ntaub ntawv neeg siv muab;",
          "Tso cai, ntawv pov thawj lossis qhov tshwm sim;",
          "Sawv cev rau lub nom tswv daws txheej txheem.",
        ]),
        p("Qhov kuaj ua ntej tsis txhais tau tias daim ntawv yuav raug lub chaw muaj cai txais lossis pom zoo."),
      ],
    },
    {
      heading: "Nqe 3. Cov cai siv",
      blocks: [
        p("Tus neeg siv yuav tsum muaj cai raws li kev cai lij choj kom siv tau lub kaw lus no."),
        p("Yog tus neeg siv tseem yau lossis muaj kev txwv, kev siv yuav tsum tau kev qhia lossis pom zoo ntawm tus sawv cev raws cai, thaum kev cai lij choj yuav tau."),
        p("Tus neeg siv yuav tsum lav ris nws lub cuab yeej, kev txuas Internet thiab kev nkag mus siv."),
        p("Lub kaw lus tej zaum muaj hom siv tsis tas yuav account. Yog muaj kev sau npe, tus neeg siv yuav tsum muab cov ntaub ntawv raug thiab tsom kwm nws tus password."),
      ],
    },
    {
      heading: "Nqe 4. Tus neeg siv lub luag haujlwm",
      blocks: [
        p("Thaum siv lub kaw lus, tus neeg siv muaj luag haujlwm:"),
        ul([
          "Muab cov ntaub ntawv tseeb, raug thiab tsim nyog rau kev kuaj daim ntawv.",
          "Tus kheej kuaj dua cov AI muab ua ntej siv mus ua txheej txheem.",
          "Tsis siv qhov tshwm sim los ua ntawv cuav lossis ua txhaum cai.",
          "Tsuas muab lwm tus tus ntaub ntawv ntiag tug thaum muaj cai thiab tau ua raws txhua nqe lus qhia lossis kev pom zoo.",
        ]),
      ],
    },
    {
      heading: "Nqe 5. Cov kev txwv tsis pub ua",
      blocks: [
        p("Tus neeg siv tsis pub:"),
        ul([
          "Siv lub kaw lus ua txhaum kev cai lij choj.",
          "Muab cov ntaub ntawv cuav lossis ua rau luag nkag siab yuam kev.",
          "Ua tus lwm tus neeg, koom haum lossis lub nom tswv.",
          "Xa tuaj kev tsov rog software lossis yam ua rau lub kaw lus puas.",
          "Tawm tsam, tshawb nrhiav qhov qhia lossis txav dhau kev ruaj ntseg.",
          "Sau ntau ntaub ntawv, luam tam sim los sis siv bot yam tsis tau kev tso cai.",
          "Siv qhov AI muab los dag luag, ua ntawv cuav lossis txav dhau lwm tus cai.",
          "Luam, hloov, faib lossis siv lag luam cov code, qhov screen, database lossis cov ntaub ntawv ntawm tus tswv, tshwj tsis yog muaj cai sau ntawv tso cai.",
        ]),
      ],
    },
    {
      heading: "Nqe 6. Cov ntaub ntawv tus neeg siv muab",
      blocks: [
        p("Lub kaw lus yuav sau tsuas yog cov ntaub ntawv tsim nyog los:"),
        ul(["Nkag siab tus neeg siv qhov xav tau;", "Muab lus qhia txheej txheem;", "Kuaj cov ntaub ntawv;", "Nrhiav qhov teeb meem technical;", "Txhim kho lub kaw lus raws li kev tso cai."]),
        p("Kev sau, khaws, siv, faib thiab rho tawm cov ntaub ntawv yuav ua raws li Txoj Cai Ceev Ntiag Tug ntawm lub kaw lus."),
        p("Txoj Cai Ceev Ntiag Tug Ntaub Ntawv tshooj 91/2025/QH15 pib siv txij hnub 1/1/2026 thiab yog hauv paus kev cai lij choj tseem ceeb rau kev ua haujlwm nrog cov ntaub ntawv ntiag tug hauv Nyab Laj."),
      ],
    },
    {
      heading: "Nqe 7. Qhov chaw tau cov ntaub ntawv txheej txheem",
      blocks: [
        p("Lub kaw lus siv lossis siv saib cov ntaub ntawv qhib rau pej xeem los ntawm:"),
        ul([
          "Cổng Dịch vụ công Quốc gia;",
          "Cov ntaub ntawv teev txog txheej txheem thoob teb chaws;",
          "Cov vev xaib ntawm cov chaw haujlwm thiab thaj tsam;",
          "Cov kev cai lij choj;",
          "Cov daim foos lub nom tswv tshaj tawm.",
        ]),
        p("Tus tswv sim ua kom cov ntaub ntawv tshiab tab sis tsis lav tias txhua yam yuav puv npo lossis tshiab txhua lub sij hawm."),
        p("Txhua qhov qhia yuav tsum qhia, thaum ua tau:"),
        ul(["Qhov chaw tau ntaub ntawv;", "Hnub hloov tshiab;", "Lub chaw tshaj tawm;", "Hauv paus kev cai lij choj;", "Qhov txuas los kuaj xyuas."]),
        p("Yog muaj kev sib txawv ntawm AI thiab cov ntaub ntawv raug cai, cov ntawm lub chaw muaj cai yuav siv ua ntej."),
      ],
    },
    {
      heading: "Nqe 8. Qhov AI tsis tuaj yeem ua",
      blocks: [
        p("Tus neeg siv nkag siab thiab pom zoo tias:"),
        ul(["AI tej zaum yuav teb tsis raug, tsis puv npo lossis tsis tshiab.", "AI tej zaum yuav nkag siab yuam kev vim tus neeg siv piav tsis txaus."]),
        p("Cov cai txheej txheem tej zaum sib txawv raws li:"),
        ul(["Thaj tsam;", "Lub sij hawm xa daim ntawv;", "Tus thov qhov xwm txheej raws cai;", "Hom cuab tam lossis tus thov;", "Cov cai hloov;", "Cov xwm txheej tshwj xeeb."]),
        p("Qhov kuaj ua ntej tsuas nrhiav tau qee hom kev yuam kev, xws li:"),
        ul(["Cov chaw tseem qhib;", "Sau tsis raug hom;", "Hnub tsis raug cai;", "Cov ntaub ntawv zoo li tsis sib xws;", "Tsis muaj cov ntawv raws li daim ntawv teev."]),
        p("Lub kaw lus tsis paub tseeb txog:"),
        ul(["Daim ntawv puas yog tseeb lossis cuav;", "Tus kos npe puas raug cai;", "Tus sau puas muaj cai txaus;", "Daim ntawv puas raug txhua yam lub chaw txais xav tau."]),
      ],
    },
    {
      heading: "Nqe 9. Kev tso kev lav ris thiab txwv",
      blocks: [
        p("Tus tswv tsis lav tias lub kaw lus yuav khiav tas mus li, tsis muaj kev yuam kev lossis raug txhua tus neeg siv qhov xav tau."),
        p("Raws li kev cai lij choj tso cai, tus tswv tsis lav rau kev puas tsuaj tshwm los ntawm tus neeg siv:"),
        ul([
          "Muab cov ntaub ntawv tsis raug;",
          "Tsis kuaj dua cov tshwm sim;",
          "Tsis piv rau cov ntawv raug cai;",
          "Siv AI dhau qhov nws pab tau;",
          "Sau cov ntaub ntawv ceeb toom tsis pub sau;",
          "Siv cov tshwm sim mus ua txhaum cai.",
        ]),
        p("Nqe no tsis rho tawm kev lav ris uas kev cai lij choj tsis pub rho, xws li kev yuam kev tim ntsej tim muag, dag ntxias lossis ua txhaum kev tiv thaiv tus neeg siv cai."),
        p("Yog lub kaw lus muab rau cov neeg siv khoom, cov cai yuav tsum raug li Txoj Cai Tiv Thaiv Tus Neeg Siv Khoom xyoo 2023, pib siv txij hnub 1/7/2024."),
      ],
    },
    {
      heading: "Nqe 10. Cai tswv ntawm kev tsim",
      blocks: [
        p("Lub npe, logo, screen, code, tsim thiab cov ntaub ntawv Nhóm Độc Bản tsim yog ntawm lawv lossis tus muab cai."),
        p("Cov ntawv cai lij choj, daim foos thiab ntaub ntawv nom tswv siv raws li txoj cai ntawm txhua qhov chaw."),
        p("Tus neeg siv siv tau qhov AI muab rau tus kheej thiab ua txheej txheem raug cai."),
        p("Tus neeg siv tsis pub hais tias qhov AI muab yog ntaub ntawv raug cai los ntawm lub nom tswv."),
      ],
    },
    {
      heading: "Nqe 11. Nres lossis txiav kev siv",
      blocks: [
        p("Tus tswv muaj cai nres lossis txiav tus neeg siv txoj cai nkag mus thaum:"),
        ul([
          "Ua txhaum cov cai no;",
          "Tawm tsam lossis ua rau lub kaw lus muaj kev phom sij;",
          "Siv lub kaw lus dag;",
          "Txav dhau lwm tus cai;",
          "Ua rau lwm tus neeg siv tsis tau siv zoo.",
        ]),
        p("Thaum muaj xwm txheej ceev txog kev ruaj ntseg, kev nres tuaj yeem ua tam sim ntawd."),
      ],
    },
    {
      heading: "Nqe 12. Kev hloov thiab kho lub kaw lus",
      blocks: [
        p("Tus tswv tuaj yeem hloov, ntxiv lossis nres ib feem ntawm lub luag haujlwm los:"),
        ul(["Kho;", "Kho qhov yuam kev;", "Txhim kho AI qauv;", "Hloov cov ntaub ntawv tshiab;", "Ua raws li kev cai lij choj;", "Ntsuas kom lub kaw lus ruaj ntseg."]),
        p("Rau kev hloov loj uas cuam tshuam tus neeg siv txoj cai, lub kaw lus yuav tsum qhia ua ntej raws li txoj kev tsim nyog."),
        p("Hnub hloov cov cai yuav tsum qhia meej saum toj kawg nkaus."),
      ],
    },
    {
      heading: "Nqe 13. Kev cai lij choj thiab kev daws teeb meem",
      blocks: [
        p("Cov cai no raug kev cai lij choj Nyab Laj tswj."),
        p("Kev tsis sib haum yuav daws ua ntej los ntawm kev sib tham zoo."),
        p("Yog daws tsis tau los ntawm kev sib tham, kev tsis sib haum yuav mus rau lub chaw muaj cai raws li kev cai lij choj Nyab Laj."),
        p("Cov cai no tsis txwv tus neeg siv txoj cai tsa suab, qhia lossis thov tiv thaiv cov ntaub ntawv ntiag tug lossis foob raug cai."),
      ],
    },
    {
      heading: "Nqe 17. Ib feem raug cai",
      blocks: [
        p("Yog ib nqe raug pom tias tsis raug cai lossis siv tsis tau, cov nqe seem yuav siv tau raws li kev cai lij choj tso cai."),
      ],
    },
    {
      heading: "Nqe 18. Cov ntaub ntawv ntawm tus tswv",
      blocks: [
        ul([
          "Lub npe: CIVI",
          "Tsim los ntawm: Nhóm Độc Bản",
          "Tus sawv cev: Nguyễn Thị Chi Ninh",
          "Email: ninh2023nguyen@gmail.com",
          "Xwm txheej: Demo sim siv",
        ]),
      ],
    },
  ],
  km: [
    {
      heading: "មាត្រា ១. អំពីប្រព័ន្ធ",
      blocks: [
        p("CIVI ត្រូវបានបង្កើតឡើងដើម្បីជួយអ្នកប្រើប្រាស់៖"),
        ul([
          "កំណត់នីតិវិធីរដ្ឋបាលដែលសមស្របនឹងតម្រូវការ;",
          "ស្វែងរកឯកសារ ទម្រង់ និងអាជ្ញាធរទទួលបន្ទុក;",
          "ទទួលបានការណែនាំជាជំហាន;",
          "ពិនិត្យជាមុននូវព័ត៌មានមុននឹងដាក់ស្នើ;",
          "រកឃើញចន្លោះខ្វះ កំហុសទម្រង់ ឬព័ត៌មានមិនស៊ីគ្នា។",
        ]),
      ],
    },
    {
      heading: "មាត្រា ២. វិសាលភាពនៃការគាំទ្ររបស់ AI",
      blocks: [
        p("AI អាចជួយអ្នកប្រើប្រាស់៖"),
        ul([
          "បំភ្លឺតម្រូវការនៃនីតិវិធី;",
          "ស្នើនីតិវិធីសមស្របតាមព័ត៌មានដែលបានផ្តល់;",
          "រាយបញ្ជីឯកសារ ទម្រង់ និងជំហានចាំបាច់;",
          "បង្ហាញឧទាហរណ៍ការបំពេញព័ត៌មានមួយចំនួន;",
          "ពិនិត្យជាមុននូវភាពពេញលេញ និងភាពស៊ីគ្នានៃទិន្នន័យ;",
          "ដាក់ប្រភពយោងសម្រាប់អ្នកប្រើផ្ទៀងផ្ទាត់។",
        ]),
        p("លទ្ធផលដែល AI បង្កើតគឺសម្រាប់គាំទ្រ និងយោងតែប៉ុណ្ណោះ។"),
        p("AI មិនមានសិទ្ធិ៖"),
        ul([
          "បញ្ជាក់ព័ត៌មានដែលអ្នកប្រើផ្តល់;",
          "ចេញអាជ្ញាប័ណ្ណ វិញ្ញាបនបត្រ ឬលទ្ធផលនីតិវិធី;",
          "តំណាងអាជ្ញាធររដ្ឋដោះស្រាយនីតិវិធីរដ្ឋបាល។",
        ]),
        p("លទ្ធផលពិនិត្យជាមុន មិនមានន័យថាឯកសារប្រាកដជាត្រូវទទួល ឬអនុម័តដោយអាជ្ញាធរមានសមត្ថកិច្ចនោះទេ។"),
      ],
    },
    {
      heading: "មាត្រា ៣. លក្ខខណ្ឌនៃការប្រើប្រាស់",
      blocks: [
        p("អ្នកប្រើប្រាស់ត្រូវមានសមត្ថភាពសមស្របតាមច្បាប់ដើម្បីប្រើប្រព័ន្ធនេះ។"),
        p("ក្នុងករណីអ្នកប្រើប្រាស់នៅជាអនីតិជន ឬមានកម្រិតសមត្ថភាព ការប្រើប្រព័ន្ធត្រូវធ្វើឡើងជាមួយការណែនាំ ឬការយល់ព្រមពីអ្នកតំណាងស្របច្បាប់ នៅពេលច្បាប់តម្រូវ។"),
        p("អ្នកប្រើប្រាស់ទទួលខុសត្រូវផ្ទាល់ខ្លួនចំពោះឧបករណ៍ ការតភ្ជាប់អ៊ីនធឺណិត និងសមត្ថភាពចូលប្រើប្រព័ន្ធ។"),
        p("ប្រព័ន្ធអាចផ្តល់របៀបប្រើប្រាស់ដោយមិនចាំបាច់មានគណនី។ ប្រសិនបើមានមុខងារចុះឈ្មោះគណនី អ្នកប្រើប្រាស់ត្រូវផ្តល់ព័ត៌មានត្រឹមត្រូវ និងការពារព័ត៌មានចូលរបស់ខ្លួន។"),
      ],
    },
    {
      heading: "មាត្រា ៤. ទំនួលខុសត្រូវរបស់អ្នកប្រើប្រាស់",
      blocks: [
        p("នៅពេលប្រើប្រព័ន្ធ អ្នកប្រើប្រាស់មានទំនួលខុសត្រូវ៖"),
        ul([
          "ផ្តល់ព័ត៌មានពិត ត្រឹមត្រូវ និងចាំបាច់សម្រាប់គោលបំណងពិនិត្យឯកសារ។",
          "ផ្ទៀងផ្ទាត់ដោយខ្លួនឯងនូវលទ្ធផលរបស់ AI មុននឹងប្រើប្រាស់ដើម្បីអនុវត្តនីតិវិធី។",
          "មិនប្រើលទ្ធផលរបស់ប្រព័ន្ធដើម្បីក្លែងបន្លំឯកសារ ប្រកាសមិនពិត ឬប្រព្រឹត្តអំពើខុសច្បាប់។",
          "ផ្តល់ទិន្នន័យផ្ទាល់ខ្លួនរបស់អ្នកដទៃតែក្នុងករណីមានមូលដ្ឋានស្របច្បាប់ និងបានបំពេញកាតព្វកិច្ចជូនដំណឹង ឬសុំការយល់ព្រមតាមការកំណត់។",
        ]),
      ],
    },
    {
      heading: "មាត្រា ៥. អំពើដែលហាមឃាត់",
      blocks: [
        p("អ្នកប្រើប្រាស់មិនត្រូវ៖"),
        ul([
          "ប្រើប្រព័ន្ធដើម្បីប្រព្រឹត្តអំពើខុសច្បាប់។",
          "ផ្តល់ព័ត៌មានក្លែងក្លាយ បង្ខូចទុច្ចរិត ឬចេតនាបង្កភាពច្រឡំ។",
          "ក្លែងបន្លំបុគ្គល អង្គការ ឬអាជ្ញាធររដ្ឋ។",
          "ផ្ទុកឡើងកូដមេរោគ កម្មវិធីបង្កគ្រោះថ្នាក់ ឬមាតិកាដែលអាចប៉ះពាល់ដល់ប្រតិបត្តិការប្រព័ន្ធ។",
          "វាយប្រហារ ស្កេនរកចន្លោះប្រហោង ជ្រៀតជ្រែកដោយគ្មានការអនុញ្ញាត ឬព្យាយាមរំលងវិធានការសុវត្ថិភាព។",
          "ប្រមូលទិន្នន័យជាចំនួនច្រើន ចម្លងស្វ័យប្រវត្តិ ឬកេងប្រវ័ញ្ចប្រព័ន្ធដោយប្រើ bot ដោយគ្មានការអនុញ្ញាត។",
          "ប្រើលទ្ធផល AI ដើម្បីបោកបញ្ឆោត ក្លែងបន្លំឯកសារ ឬរំលោភសិទ្ធិ និងផលប្រយោជន៍ស្របច្បាប់របស់អ្នកដទៃ។",
          "ចម្លង កែប្រែ ចែកចាយ ឬកេងប្រវ័ញ្ចពាណិជ្ជកម្មនូវកូដប្រភព ចំណុចប្រទាក់ មូលដ្ឋានទិន្នន័យ ឬមាតិកាដែលជាកម្មសិទ្ធិរបស់ប្រតិបត្តិករ លើកលែងតែមានការអនុញ្ញាតជាលាយលក្ខណ៍អក្សរ។",
        ]),
      ],
    },
    {
      heading: "មាត្រា ៦. ទិន្នន័យដែលអ្នកប្រើប្រាស់ផ្តល់",
      blocks: [
        p("ប្រព័ន្ធគួរប្រមូលតែទិន្នន័យចាំបាច់ដើម្បី៖"),
        ul(["យល់តម្រូវការរបស់អ្នកប្រើប្រាស់;", "ផ្តល់ការណែនាំនីតិវិធី;", "ពិនិត្យព័ត៌មាន;", "រកឃើញកំហុសបច្ចេកទេស;", "ធ្វើឱ្យប្រព័ន្ធប្រសើរឡើងក្នុងវិសាលភាពដែលអនុញ្ញាត។"]),
        p("ការប្រមូល រក្សាទុក ប្រើប្រាស់ ចែករំលែក និងលុបទិន្នន័យ ត្រូវអនុវត្តតាមគោលការណ៍ការពារទិន្នន័យផ្ទាល់ខ្លួនរបស់ប្រព័ន្ធ។"),
        p("ច្បាប់ស្តីពីការការពារទិន្នន័យផ្ទាល់ខ្លួន លេខ 91/2025/QH15 មានប្រសិទ្ធភាពចាប់ពីថ្ងៃទី 1/1/2026 និងជាមូលដ្ឋានច្បាប់សំខាន់សម្រាប់សកម្មភាពដំណើរការទិន្នន័យផ្ទាល់ខ្លួននៅវៀតណាម។"),
      ],
    },
    {
      heading: "មាត្រា ៧. ប្រភពទិន្នន័យនីតិវិធីរដ្ឋបាល",
      blocks: [
        p("ប្រព័ន្ធប្រើប្រាស់ ឬយោងទិន្នន័យសាធារណៈពីប្រភពដូចជា៖"),
        ul([
          "វិបផតថលសេវាសាធារណៈជាតិ;",
          "មូលដ្ឋានទិន្នន័យជាតិស្តីពីនីតិវិធីរដ្ឋបាល;",
          "វិបផតថលរបស់ក្រសួង ស្ថាប័ន និងមូលដ្ឋាន;",
          "ឯកសារច្បាប់;",
          "ទម្រង់រដ្ឋបាលដែលបានចេញផ្សាយដោយអាជ្ញាធរមានសមត្ថកិច្ច។",
        ]),
        p("ប្រតិបត្តិករព្យាយាមធ្វើបច្ចុប្បន្នភាពទិន្នន័យជាប្រចាំ ប៉ុន្តែមិនធានាថាព័ត៌មានទាំងអស់តែងតែពេញលេញ ឬថ្មីបំផុតគ្រប់ពេលនោះទេ។"),
        p("រាល់ការណែនាំគួរបង្ហាញ នៅពេលអាចធ្វើបាន៖"),
        ul(["ប្រភពទិន្នន័យ;", "កាលបរិច្ឆេទធ្វើបច្ចុប្បន្នភាព;", "អាជ្ញាធរចេញផ្សាយ;", "មូលដ្ឋានច្បាប់;", "តំណភ្ជាប់សម្រាប់ផ្ទៀងផ្ទាត់។"]),
        p("ក្នុងករណីមានភាពខុសគ្នារវាងលទ្ធផល AI និងព័ត៌មានផ្លូវការ ព័ត៌មានដែលចេញផ្សាយដោយអាជ្ញាធរមានសមត្ថកិច្ចត្រូវប្រើអាទិភាព។"),
      ],
    },
    {
      heading: "មាត្រា ៨. ដែនកំណត់នៃលទ្ធផល AI",
      blocks: [
        p("អ្នកប្រើប្រាស់យល់ និងទទួលស្គាល់ថា៖"),
        ul(["AI អាចឆ្លើយខុស មិនពេញលេញ ឬមិនទាន់ធ្វើបច្ចុប្បន្នភាព។", "AI អាចយល់ស្ថានភាពខុសដោយសារការពិពណ៌នារបស់អ្នកប្រើមិនពេញលេញ។"]),
        p("តម្រូវការនីតិវិធីអាចខុសគ្នាតាម៖"),
        ul(["មូលដ្ឋាន;", "ពេលវេលាដាក់ស្នើ;", "ស្ថានភាពច្បាប់របស់អ្នកស្នើសុំ;", "ប្រភេទទ្រព្យសម្បត្តិ ឬវត្ថុ;", "បទប្បញ្ញត្តិផ្លាស់ប្តូរ;", "ករណីពិសេស។"]),
        p("មុខងារពិនិត្យជាមុនអាចរកឃើញតែកំហុសមួយចំនួន ឧទាហរណ៍៖"),
        ul(["វាលនៅទទេ;", "ទម្រង់មិនត្រឹមត្រូវ;", "កាលបរិច្ឆេទមិនត្រឹមត្រូវ;", "ទិន្នន័យមានសញ្ញាមិនស៊ីគ្នា;", "ខ្វះឯកសារតាមបញ្ជីដែលបានដឹង។"]),
        p("ប្រព័ន្ធមិនអាចកំណត់ច្បាស់លាស់នូវ៖"),
        ul([
          "ឯកសារពិត ឬក្លែងក្លាយ;",
          "ហត្ថលេខាត្រឹមត្រូវឬអត់;",
          "អ្នកប្រកាសមានសិទ្ធិគ្រប់គ្រាន់ឬអត់;",
          "ឯកសារបំពេញគ្រប់តម្រូវការជាក់ស្តែងរបស់អាជ្ញាធរទទួលឬអត់។",
        ]),
      ],
    },
    {
      heading: "មាត្រា ៩. ការលើកលែង និងកម្រិតទំនួលខុសត្រូវ",
      blocks: [
        p("ប្រតិបត្តិករមិនធានាថាប្រព័ន្ធនឹងដំណើរការជាបន្តបន្ទាប់ គ្មានកំហុស ឬបំពេញគ្រប់តម្រូវការរបស់អ្នកប្រើប្រាស់ទេ។"),
        p("ក្នុងវិសាលភាពដែលច្បាប់អនុញ្ញាត ប្រតិបត្តិករមិនទទួលខុសត្រូវចំពោះការខូចខាតកើតឡើងផ្ទាល់ពីអ្នកប្រើប្រាស់៖"),
        ul([
          "ផ្តល់ព័ត៌មានមិនត្រឹមត្រូវ;",
          "មិនផ្ទៀងផ្ទាត់លទ្ធផលឡើងវិញ;",
          "មិនប្រៀបធៀបជាមួយប្រភពផ្លូវការ;",
          "ប្រើ AI ក្រៅវិសាលភាពគាំទ្រ;",
          "បញ្ចូលទិន្នន័យរសើបផ្ទុយពីការព្រមាន;",
          "ប្រើលទ្ធផលដើម្បីប្រព្រឹត្តអំពើខុសច្បាប់។",
        ]),
        p("ខមាត្រានេះមិនលើកលែងទំនួលខុសត្រូវដែលច្បាប់មិនអនុញ្ញាតឱ្យលើកលែងឡើយ រួមទាំងទំនួលខុសត្រូវកើតចេញពីអំពើចេតនាល្មើស ក្លែងបន្លំ ឬល្មើសកាតព្វកិច្ចការពារសិទ្ធិស្របច្បាប់របស់អ្នកប្រើប្រាស់។"),
        p("ប្រសិនបើប្រព័ន្ធផ្តល់ជូនអ្នកប្រើប្រាស់ជាអ្នកប្រើប្រាស់ (consumer) ការរៀបចំ និងអនុវត្តលក្ខខណ្ឌត្រូវស្របតាមច្បាប់ការពារសិទ្ធិអ្នកប្រើប្រាស់ឆ្នាំ 2023 មានប្រសិទ្ធភាពចាប់ពីថ្ងៃទី 1/7/2024។"),
      ],
    },
    {
      heading: "មាត្រា ១០. កម្មសិទ្ធិបញ្ញា",
      blocks: [
        p("ឈ្មោះ ស្លាកសញ្ញា ចំណុចប្រទាក់ កូដប្រភព ការរចនា ឯកសារបច្ចេកទេស និងមាតិកាដែលបង្កើតឡើងដោយ Nhóm Độc Bản ជាកម្មសិទ្ធិរបស់អង្គភាពនេះ ឬអ្នកផ្តល់អាជ្ញាប័ណ្ណដែលពាក់ព័ន្ធ។"),
        p("ឯកសារច្បាប់ ទម្រង់ និងទិន្នន័យរដ្ឋបាល ត្រូវប្រើប្រាស់តាមរបបច្បាប់អនុវត្តចំពោះប្រភពនីមួយៗ។"),
        p("អ្នកប្រើប្រាស់អាចប្រើលទ្ធផល AI សម្រាប់គោលបំណងផ្ទាល់ខ្លួន និងអនុវត្តនីតិវិធីស្របច្បាប់។"),
        p("អ្នកប្រើប្រាស់មិនត្រូវប្រកាសថាលទ្ធផល AI ជាព័ត៌មានផ្លូវការចេញផ្សាយដោយអាជ្ញាធររដ្ឋឡើយ។"),
      ],
    },
    {
      heading: "មាត្រា ១១. ការផ្អាក ឬបញ្ចប់សិទ្ធិប្រើប្រាស់",
      blocks: [
        p("ប្រតិបត្តិករមានសិទ្ធិផ្អាក ឬបញ្ចប់សិទ្ធិចូលប្រើនៅពេលអ្នកប្រើប្រាស់៖"),
        ul([
          "ល្មើសលក្ខខណ្ឌនេះ;",
          "មានអំពើវាយប្រហារ ឬបង្កគ្រោះថ្នាក់ដល់ប្រព័ន្ធ;",
          "ប្រើប្រព័ន្ធដើម្បីក្លែងបន្លំ;",
          "រំលោភសិទ្ធិរបស់អ្នកដទៃ;",
          "ធ្វើឱ្យប៉ះពាល់ដល់ការប្រើប្រាស់របស់អ្នកប្រើប្រាស់ដទៃ។",
        ]),
        p("ក្នុងករណីអាសន្នស្តីពីសុវត្ថិភាព ការផ្អាកអាចធ្វើឡើងភ្លាមៗ។"),
      ],
    },
    {
      heading: "មាត្រា ១២. ការផ្លាស់ប្តូរ និងថែទាំប្រព័ន្ធ",
      blocks: [
        p("ប្រតិបត្តិករអាចកែប្រែ បន្ថែម ឬបញ្ឈប់មុខងារមួយចំនួនដើម្បី៖"),
        ul(["ថែទាំ;", "ជួសជុលកំហុស;", "ធ្វើឱ្យប្រសើរឡើងម៉ូដែល AI;", "ធ្វើបច្ចុប្បន្នភាពទិន្នន័យ;", "អនុវត្តតាមតម្រូវការច្បាប់;", "ធានាសុវត្ថិភាពប្រព័ន្ធ។"]),
        p("សម្រាប់ការផ្លាស់ប្តូរសំខាន់ៗដែលប៉ះពាល់ដល់សិទ្ធិអ្នកប្រើប្រាស់ ប្រព័ន្ធគួរជូនដំណឹងជាមុនតាមមធ្យោបាយសមស្រប។"),
        p("កាលបរិច្ឆេទធ្វើបច្ចុប្បន្នភាពលក្ខខណ្ឌត្រូវបង្ហាញយ៉ាងច្បាស់នៅផ្នែកខាងលើទំព័រ។"),
      ],
    },
    {
      heading: "មាត្រា ១៣. ច្បាប់អនុវត្ត និងការដោះស្រាយវិវាទ",
      blocks: [
        p("លក្ខខណ្ឌនេះស្ថិតក្រោមច្បាប់វៀតណាម។"),
        p("វិវាទត្រូវដោះស្រាយជាមុនតាមរយៈការចរចា និងការផ្លាស់ប្តូរដោយភាពស្មោះត្រង់។"),
        p("ប្រសិនបើមិនអាចដោះស្រាយដោយការចរចា វិវាទត្រូវដោះស្រាយនៅអាជ្ញាធរមានសមត្ថកិច្ចតាមច្បាប់វៀតណាម។"),
        p("លក្ខខណ្ឌនេះមិនកម្រិតសិទ្ធិប្តឹងតវ៉ា ជូនដំណឹង ស្នើសុំការការពារទិន្នន័យផ្ទាល់ខ្លួន ឬសិទ្ធិប្តឹងក្តីស្របច្បាប់របស់អ្នកប្រើប្រាស់ឡើយ។"),
      ],
    },
    {
      heading: "មាត្រា ១៧. សុពលភាពដោយផ្នែក",
      blocks: [
        p("ប្រសិនបើប្រការណាមួយត្រូវបានកំណត់ថាមិនត្រឹមត្រូវ ឬមិនអាចអនុវត្តបាន ប្រការដែលនៅសល់នៅតែមានសុពលភាពក្នុងវិសាលភាពដែលច្បាប់អនុញ្ញាត។"),
      ],
    },
    {
      heading: "មាត្រា ១៨. ព័ត៌មានប្រតិបត្តិករ",
      blocks: [
        ul([
          "ឈ្មោះគម្រោង: CIVI",
          "អង្គភាពអភិវឌ្ឍ: Nhóm Độc Bản",
          "អ្នកតំណាង/ទទួលបន្ទុក: Nguyễn Thị Chi Ninh",
          "អ៊ីមែល: ninh2023nguyen@gmail.com",
          "ស្ថានភាព: ជំនាន់សាកល្បង",
        ]),
      ],
    },
  ],
};

export const privacyMeta = {
  lastUpdated: "18/7/2026",
};
