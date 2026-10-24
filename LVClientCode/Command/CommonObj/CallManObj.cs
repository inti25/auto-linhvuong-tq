using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
using LVClient.Common;

namespace LVClient.Command.CommonObj
{
	public class CallManObj : Command.CityObj.MilitaryGeneral
	{
		public int GroupID;
		/// <summary>
		/// Danh sách LVClient.Command.CommonObj.ManOBJ
		/// </summary>
		public ArrayList Mans = new ArrayList();
	
		public int TimeToCheck;

		public bool TuMuaManTocLenh = false;
		public int ToaDoCallVeX;
		public int ToaDoCallVeY;
		public int SoTuongMinhDanh1TuongDich = 1;
	


		public override string ToString()
		{
			string str = "Cử " + this.GeneralName;
			str += " đánh ";

			for (int i = 0; i < Mans.Count; i++)
			{
				str += ((LVClient.Command.CommonObj.ManOBJ)Mans[i]).ManName + ", ";
			}

			str += " được gọi về (" + ToaDoCallVeX + ", " + ToaDoCallVeY + ")";
			str +=  ", phương thức tấn công " + this.PhuongThucTanCongName + ", mục tiêu " + this.PhuongThucChonMucTieuName;
			if (this.TuUpSiKhi)
			{
				str = str + ", có nâng sk";
			}
			else
			{
				str = str + ", không nâng sk";
			}

			if (this.TuMuaManTocLenh)
			{
				str = str + ", có mua man lệnh";
			}
			else
			{
				str = str + ", không mua man lệnh";
			}

			str += ", mưu kế " + LVClient.Common.WarFunc.GetMuuKeTrongChienTruongName(this.MuuKeTrongChienTranID);
			str += ", qsố min " + this.SoLuongQuanMinToGo + ", sk min " + this.SiKhiMinToGo ;

			if (this.TuBienCheQuan)
				str += ". Bchế " + this.Military.Bobinh[0] + " bộ, " + this.Military.KyBinh[0] + " kỵ, " + this.Military.CungThu[0] + " cung, " + this.Military.Xe[0] + " xe";
			else
				str += ". Không biên chế thêm quân";

			str += ". Quân giới: bộ " + Wepons.GetWeponName(this.Military.Bobinh[1]);
			str += "-" + Wepons.GetWeponName(this.Military.Bobinh[2]) + "-" + Wepons.GetWeponName(this.Military.Bobinh[3]);
			str += ", kỵ " + Wepons.GetWeponName(this.Military.KyBinh[1]) + "-" + Wepons.GetWeponName(this.Military.KyBinh[2]) + "-" + Wepons.GetWeponName(this.Military.KyBinh[3]);
			str += ", cung " + Wepons.GetWeponName(this.Military.CungThu[1]) + "-" + Wepons.GetWeponName(this.Military.CungThu[2]) + "-" + Wepons.GetWeponName(this.Military.CungThu[3]) + ", xe " + Wepons.GetWeponName(this.Military.Xe[1]);

			return str;
		}

        // 
        /// <summary>
        /// sắp xếp theo tổng số quân giảm dần
        /// </summary>
        /// <param name="obj"></param>
        /// <returns></returns>
        public override int CompareTo(object obj)
        {
            string str1;
            string str2;
            if (obj is CallManObj)
            {
                CallManObj temp = (CallManObj)obj;
               //str1 = temp.GroupID & temp.ToaDoCallVeX & temp.ToaDoCallVeY

                return temp.Military.SoQuanDangCo.CompareTo(this.Military.SoQuanDangCo);
            }
            throw new ArgumentException("object is not a Temperature");
        }

	}
}
