using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;

namespace LVClient.Common
{

	public class Wepons
	{
		public string name;
		public int id;
		public int type;  //1: vu khi, 2: giap, 3: ngua, xe
		public static Hashtable wepon = new Hashtable();
		public static Wepons[] arWepon = new Wepons[68] ; 
		static Wepons()
		{
			
			int i = 0;

			arWepon[i] = new Wepons(0, "Để nguyên", 0);
			i++;arWepon[i] = new Wepons(101,"Thấu giáp thương",1);
			i++;arWepon[i] = new Wepons(102,"Hậu bối đao",1);
			i++;arWepon[i] = new Wepons(103, "Hổ bí đao", 1);
			i++;arWepon[i] = new Wepons(104, "Cổ đồng đao", 1);
			i++;arWepon[i] = new Wepons(105, "Đại khảm đao", 1);
			i++;arWepon[i] = new Wepons(106, "Khoan nhận kiếm", 1);
			i++;arWepon[i] = new Wepons(107, "Tam hoàn đại đao", 1);
			i++;arWepon[i] = new Wepons(108, "Bách thắng trường đao", 1);
			i++;arWepon[i] = new Wepons(111, "Đoản thiết kiếm", 1);
            i++;arWepon[i] = new Wepons(112, "Hổ ảnh đao", 1);
            i++;arWepon[i] = new Wepons(121, "Huyền thiết kiếm", 1);
            i++;arWepon[i] = new Wepons(122, "Phá thiên kích", 1);
            i++;arWepon[i] = new Wepons(131, "Thôn nhật trảm", 1);
            i++;arWepon[i] = new Wepons(132, "Liệt hỏa kiếm", 1);
            i++;arWepon[i] = new Wepons(150, "Đông dương đao", 1);
			i++;arWepon[i] = new Wepons(151, "Thú vương thương", 1);
			i++;arWepon[i] = new Wepons(152, "Đồ mã qua", 1);
			i++;arWepon[i] = new Wepons(201, "Thiết thai cung", 1);
			i++;arWepon[i] = new Wepons(202, "Bá vương nỗ", 1);
			i++;arWepon[i] = new Wepons(203, "Ly tần cung", 1);
			i++;arWepon[i] = new Wepons(204, "Bảo điêu cung", 1);
			i++;arWepon[i] = new Wepons(205, "Ngọc giác cung", 1);
			i++;arWepon[i] = new Wepons(206, "Trường huyền giáp cung", 1);
			i++;arWepon[i] = new Wepons(207, "Thần diên cung", 1);
			i++;arWepon[i] = new Wepons(208, "Phá phong cung", 1);
            i++;arWepon[i] = new Wepons(211, "Nhật nguyệt canh cung", 1);
			i++;arWepon[i] = new Wepons(212, "Nhận mộc hồ cung", 1);
            i++;arWepon[i] = new Wepons(221, "Thấu bối cách cung", 1);
            i++;arWepon[i] = new Wepons(222, "Mông cổ cường cung", 1);
            i++;arWepon[i] = new Wepons(231, "Thu nguyệt hành thiên cung", 1);
            i++;arWepon[i] = new Wepons(232, "Sáp huyết vương cung", 1);
            i++;arWepon[i] = new Wepons(250, "Ngưu giác cung", 1);
			i++;arWepon[i] = new Wepons(251, "Xạ ảnh cung", 1);
			i++;arWepon[i] = new Wepons(301, "Ngư lân giáp", 2);
			i++;arWepon[i] = new Wepons(302, "Tinh cương giáp", 2);
			i++;arWepon[i] = new Wepons(303, "Minh quang chiến giáp", 2);
			i++;arWepon[i] = new Wepons(304, "Địa long chiến giáp", 2);
			i++;arWepon[i] = new Wepons(305, "Thiên hộ giáp", 2);
			i++;arWepon[i] = new Wepons(306, "Thảo nghịch khôi giáp", 2);
			i++;arWepon[i] = new Wepons(307, "Xích nhật chiến giáp", 2);
			i++;arWepon[i] = new Wepons(308, "Lôi đình chiến giáp", 2);
            i++;arWepon[i] = new Wepons(311, "Tướng quân chiến giáp", 2);
            i++;arWepon[i] = new Wepons(312, "Hổ ủng giáp trụ", 2);
            i++;arWepon[i] = new Wepons(321, "Cấm vệ giáp", 2);
            i++;arWepon[i] = new Wepons(322, "Huyền thiết giáp trụ", 2);
            i++;arWepon[i] = new Wepons(331, "Chiến nguyện hộ giáp", 2);
            i++;arWepon[i] = new Wepons(332, "Chiến thần chi trụ", 2);
            i++;arWepon[i] = new Wepons(350, "Đằng du giáp", 2);
			i++;arWepon[i] = new Wepons(401, "Tuyệt địa mã", 3);
			i++;arWepon[i] = new Wepons(402, "Phiên vũ mã", 3);
			i++;arWepon[i] = new Wepons(403, "Bôn tiêu mã", 3);
			i++;arWepon[i] = new Wepons(404, "Dã hành mã", 3);
			i++;arWepon[i] = new Wepons(405, "Việt ảnh mã", 3);
			i++;arWepon[i] = new Wepons(406, "Du huy mã", 3);
			i++;arWepon[i] = new Wepons(407, "Thiết kị mã", 3);
			i++;arWepon[i] = new Wepons(408, "Xích ký mã", 3);
            i++;arWepon[i] = new Wepons(411, "Siêu quang mã", 3);
			i++;arWepon[i] = new Wepons(412, "Đằng vụ mã", 3);
            i++;arWepon[i] = new Wepons(421, "Hiệp dực mã", 3);
            i++;arWepon[i] = new Wepons(422, "Đạo ly mã", 3);
            i++;arWepon[i] = new Wepons(431, "Hoa lưu mã", 3);
            i++;arWepon[i] = new Wepons(432, "Truy phong mã", 3);
            i++;arWepon[i] = new Wepons(450, "Hung Nô phiêu kị", 3);
            i++;arWepon[i] = new Wepons(501, "Xe ném đá loại nhẹ", 4);
            i++;arWepon[i] = new Wepons(511, "Xe ném đá loại vừa", 4);
            i++;arWepon[i] = new Wepons(521, "Xe ném đá loại nặng", 4);
			i++;arWepon[i] = new Wepons(531, "Xe ném đá hỏa diêm", 4);

			for (int ii=0; ii < arWepon.Length; ii++)
			{					
				wepon.Add(arWepon[ii].id, arWepon[ii].name);
			}
			
			
			/*
			wepon.Add(101,"Thấu giáp thương");
			wepon.Add(102,"Hậu bối đao");
			wepon.Add(103,"Hổ bí đao");
			wepon.Add(104,"Cổ đồng đao");
			wepon.Add(105,"Đại khảm đao");
			wepon.Add(106,"Khoan nhận kiếm");
			wepon.Add(107,"Tam hoàn đại đao");
			wepon.Add(150,"Đông dương đao");
			wepon.Add(151,"Thú vương thương");
			wepon.Add(152,"Đồ mã qua");
			wepon.Add(201,"Thiết thai cung");
			wepon.Add(202,"Bá vương nỗ");
			wepon.Add(203,"Ly tần cung");
			wepon.Add(204,"Bảo điêu cung");
			wepon.Add(205,"Ngọc giác cung");
			wepon.Add(206,"Trường huyền giáp cung");
			wepon.Add(207,"Thần diên cung");
			wepon.Add(250,"Ngưu giác cung");
			wepon.Add(251,"Xạ ảnh cung");
			wepon.Add(301,"Ngư lân giáp");
			wepon.Add(302,"Tinh cương giáp");
			wepon.Add(303,"Minh quang chiến giáp");
			wepon.Add(304,"Địa long chiến giáp");
			wepon.Add(305,"Thiên hộ giáp");
			wepon.Add(306,"Thảo nghịch khôi giáp");
			wepon.Add(307,"Xích nhật chiến giáp");
			wepon.Add(350,"Đằng du giáp");
			wepon.Add(401,"Tuyệt địa mã");
			wepon.Add(402,"Phiên vũ mã");
			wepon.Add(403,"Bôn tiêu mã");
			wepon.Add(404,"Dã hành mã");
			wepon.Add(405,"Việt ảnh mã");
			wepon.Add(406,"Du huy mã");
			wepon.Add(407,"Thiết kị mã");
			wepon.Add(501, "Xe ném đá loại nhẹ");
			
			arWepon = new Wepons[wepon.Count];		
			int[] arKey = new int[wepon.Count];
			wepon.Keys.CopyTo(arKey, 0);
			Array.Sort(arKey);
			for (int i = 0; i < wepon.Count; i++)
			{
				arWepon[i] = new Wepons(arKey[i], wepon[arKey[i]].ToString());
			}
			 * */
		}

		public Wepons(int id, string name)
		{
			this.name = name;
			this.id = id;
		}
		public Wepons(int id, string name, int type)
		{
			this.name = name;
			this.id = id;
			this.type = type;
		}

		public override string ToString()
		{
			return this.name;
		}
		public static string GetWeponName(int WpID)
		{
			try
			{
				return wepon[WpID].ToString();
			}
			catch (Exception ex)
			{
				return "Unknow";
			}
		}
	}
}



/*
0. Để nguyên
101.Thấu giáp thương
102.Hậu bối đao
103. Hổ bí đao
104. Cổ đồng đao
105. Đại khảm đao
106. Khoan nhận kiếm
107. Tam hoàn đại đao
150. Đông dương đao
151. Thú vương thương
152. Đồ mã qua
201. Thiết thai cung
202. Bá vương nỗ
203. Ly tần cung
204. Bảo điêu cung
205. Ngọc giác cung
206. Trường huyền giáp cung
207. Thần diên cung
211. Nhật nguyệt canh cung
250. Ngưu giác cung
251. Xạ ảnh cung
301. Ngư lân giáp
302. Tinh cương giáp
303. Minh quang chiến giáp
304. Địa long chiến giáp
305. Thiên hộ giáp
306. Thảo nghịch khôi giáp
307. Xích nhật chiến giáp
350. Đằng du giáp
401. Tuyệt địa mã
402. Phiên vũ mã
403. Bôn tiêu mã
404. Dã hành mã
405. Việt ảnh mã
406. Du huy mã
407. Thiết kị mã
411. Siêu quang mã
501. Xe ném đá loại nhẹ. 
 * 
 */




/*


0. Để nguyên
101. Thấu giáp thương
102. Hậu bối đao
103. Hổ bí đao
104. Cổ đồng đao
105. Đại khảm đao
106. Khoan nhận kiếm
107. Tam hoàn đại đao
108. Bách thắng trường đao
111. Đoản thiết kiếm
112. Hổ ảnh đao
121. Huyền thiết kiếm
122. Phá thiên kích
131. Thôn nhật trảm
132. Liệt hỏa kiếm
150. Đông dương đao
151. Thú vương thương
152. Đồ mã qua
201. Thiết thai cung
202. Bá vương nỗ
203. Ly tần cung
204. Bảo điêu cung
205. Ngọc giác cung
206. Trường huyền giáp cung
207. Thần diên cung
208. Phá phong cung
211. Nhật nguyệt canh cung
212. Nhận mộc hồ cung
221. Thấu bối cách cung
222. Mông cổ cường cung
231. Thu nguyệt hành thiên cung
232. Sáp huyết vương cung
250. Ngưu giác cung
251. Xạ ảnh cung
301. Ngư lân giáp
302. Tinh cương giáp
303. Minh quang chiến giáp
304. Địa long chiến giáp
305. Thiên hộ giáp
306. Thảo nghịch khôi giáp
307. Xích nhật chiến giáp
308. Lôi đình chiến giáp
311. Tướng quân chiến giáp
312. Hổ ủng giáp trụ
321. Cấm vệ giáp
322. Huyền thiết giáp trụ
331. Chiến nguyện hộ giáp
332. Chiến thần chi trụ
350. Đằng du giáp
401. Tuyệt địa mã
402. Phiên vũ mã
403. Bôn tiêu mã
404. Dã hành mã
405. Việt ảnh mã
406. Du huy mã
407. Thiết kị mã
408. Xích ký mã
411. Siêu quang mã
412. Đằng vụ mã
421. Hiệp dực mã
422. Đạo ly mã
431. Hoa lưu mã
432. Truy phong mã
450. Hung Nô phiêu kị
501. Xe ném đá loại nhẹ
511. Xe ném đá loại vừa
521. Xe ném đá loại nặng
531. Xe ném đá hỏa diêm

*/