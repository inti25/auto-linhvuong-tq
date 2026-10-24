using System;
using System.Collections.Generic;
using System.Collections;
using System.Text;

namespace LVClient.Command.OPTObj 
{
    public class GeneralInCombat : LVClient.Command.CityObj.MilitaryGeneral 
	{
        /*/[1,"dai ca",14928,"Tư Qúy",358486,"Prepare for War",23910,4571922,1,87,0,0,6000,0,0,0,0,0,"",1]
        //                  3ten      4id                                   8battlearray
        //[11,"",0,"Sơn tặc",0,"",0,0,2,100,0,507,0,0,0,0,0,0,"",16]
		/
		 *0: số thứ tự đạo quân trong chiến trường
		 *1: tên thành chủ 
		 *2: uid - userid
		 *3: Tên tướng
		 *4: GeneralID
		 *5: Tên thành xuất binh
		 *6: cityID - id thành xuất binh
		 *7: 
		 *8: Trận hình
		 *9: Sỹ khí
		 *10: Trạng thái quân. 0: bình thường, 1: hỗn loạn, 2: , 3: thiếu kỷ luật 
		 *11: bộ binh
		 *12: kỵ binh
		 *13: cung thủ
		 *14: xe
		 *15: Phương thức tấn công. 0: tùy chọn, 1:Tấn công phổ thông, 2: Đơn Chiến, 3: Phòng ngự, 4: Rút lui, 
		 *							10: Đột kích, 11: Mãnh công, 12: Thủy công, 13: Hỏa tiễn, 14: Phản kích
		 *							
		 *16: Mục tiêu đánh (= [0]). 0:Tùy chọn
		 *17: ID quân sư
		 *18: Tên quân sư
		 *19:
		
		 */ 
		//public int id = 0;
        public int attackid = 0;	// số thứ tự quân trong chiến trường
        //public string name = "";
		public int UserID;
		public int PhuongThucDangTanCong;	// Phương thức sẽ tấn công	
		//public int PhuongThucSeTanCong = 13;	// Phương thức sẽ tấn công	

	
		public int TagetID;			// mục tiêu sẽ đánh
		public GeneralInCombat(ArrayList generaldata) 
		{
			attackid	= int.Parse(generaldata[0].ToString());
			UserID		= int.Parse(generaldata[2].ToString());
			GeneralName = generaldata[3].ToString();
			GeneralId	= int.Parse(generaldata[4].ToString());
			CityID = int.Parse(generaldata[6].ToString());
			this.Military.TranHinh = int.Parse(generaldata[8].ToString());
			this.Military.SyKhi = int.Parse(generaldata[9].ToString());
			this.Military.TrangThaiQuanDoi = int.Parse(generaldata[10].ToString());
			this.Military.Bobinh[0] = int.Parse(generaldata[11].ToString());
			this.Military.KyBinh[0] = int.Parse(generaldata[12].ToString());
			this.Military.CungThu[0] = int.Parse(generaldata[13].ToString());
			this.Military.Xe[0] = int.Parse(generaldata[14].ToString());
			this.Military.SoQuanDangCo = this.Military.Bobinh[0] + this.Military.KyBinh[0] + this.Military.CungThu[0] + this.Military.Xe[0] * 3;
			this.PhuongThucDangTanCong = int.Parse(generaldata[15].ToString());
			this.TagetID = int.Parse(generaldata[16].ToString());
			
		}

        
    }
}
