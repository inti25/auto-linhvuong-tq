using System;
using System.Collections.Generic;
using System.Text;

namespace LVClient.Command.CommonObj
{
    using LVClient.Command.CityObj;
    using LVClient.Common;
    using System;

	public class BinhManObj :  Command.CityObj.MilitaryGeneral
    {
        public int ManID=0;
        public string ManName="";
        public int MaxOToGo;
        //public int MinQuanSo;
        //public int MinSyKhi;
        //public int PhuongThucChonMucTieuID;
        //public string PhuongThucChonMucTieuName;
        //public int PhuongThucTanCongID;
        //public string PhuongThucTanCongName;
        public int SoTuongMinhDanh1TuongDich = 1;
        public int TimeToCheck;
        public int UuTienID;
        public string UuTienName;
        
        /// <summary>
        /// // 1: cacs loai man; 14: Dia tinh trong mo 
        /// </summary>
        public int ManType=0;

        public int ToaDoMoX = 0;
        public int ToaDoMoY = 0;

		//public bool CoNangSyKhi;
		//public MilitaryGeneral General = new MilitaryGeneral();

        public override int CompareTo(object obj)
        {
            if (!(obj is BinhManObj))
            {
                throw new ArgumentException("object is not a Temperature");
            }
            BinhManObj obj2 = (BinhManObj) obj;
            if (this.CityID != obj2.CityID)
            {
                return this.CityID.CompareTo(obj2.CityID);
            }
            if (this.GeneralId != obj2.GeneralId)
            {
                return this.GeneralId.CompareTo(obj2.GeneralId);
            }
            return this.ManID.CompareTo(obj2.ManID);
        }

        public override string ToString()
        {
            string str = "Cử " + this.GeneralName + " từ " + this.CityName ;
            if (this.ManType == 14)
                str += " đánh Địa tinh ở tọa độ (" + this.ToaDoMoX + ", " + ToaDoMoY + ")";
            else
                str += " đánh " + this.ManName;

            //str += ", " + this.UuTienName;
 
            str += ", " + this.PhuongThucTanCongName;
			str += ", mục tiêu " + this.PhuongThucChonMucTieuName;
           if (this.TuUpSiKhi)
            {
                str = str + ", có nâng sk";
            }
            else
            {
				str = str + ", không nâng sk";
            }

		   str += ", mưu kế " + LVClient.Common.WarFunc.GetMuuKeTrongChienTruongName(this.MuuKeTrongChienTranID);
		   str += ", qsố min " +  this.SoLuongQuanMinToGo + ", sk min " +  this.SiKhiMinToGo +  ", max ô đi " + this.MaxOToGo ;
		   str += ". Bchế "+ this.Military.Bobinh[0]+ " bộ, "+ this.Military.KyBinh[0]+ " kỵ, "+ this.Military.CungThu[0]+ " cung, "+ this.Military.Xe[0]+ " xe, " ;
           str += ". Quân giới: bộ " + Wepons.GetWeponName(this.Military.Bobinh[1])+ "-" + Wepons.GetWeponName(this.Military.Bobinh[2]) + "-" + Wepons.GetWeponName(this.Military.Bobinh[3]);
		   str +=  ", kỵ " + Wepons.GetWeponName(this.Military.KyBinh[1]) + "-" + Wepons.GetWeponName(this.Military.KyBinh[2]) + "-" + Wepons.GetWeponName(this.Military.KyBinh[3]);
			str +=  ", cung " + Wepons.GetWeponName(this.Military.CungThu[1]) + "-" + Wepons.GetWeponName(this.Military.CungThu[2]) + "-" + Wepons.GetWeponName(this.Military.CungThu[3]) + ", xe " + Wepons.GetWeponName(this.Military.Xe[1]);
			 
			return str;
		}
    }
}

