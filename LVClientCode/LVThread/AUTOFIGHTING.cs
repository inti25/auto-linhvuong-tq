using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
using System.Threading;

namespace LVClient.LVThread
{
	public class AUTOFIGHTING : LVClient.LVThread.ThreadSkeleton  
	{
		public static ArrayList BattleIDList = new ArrayList();
		public static ArrayList BattleIDRunning = new ArrayList();

		private int SleeptimeInSecond;					// giây
		private int Battleid = 0;
		private int SoTuongDanh1TuongDich = 1;		//0: mục tiêu tùy chọn, 1: 1&1, 2: 2&1: 3: 3&1 ............. 
	
		private int TotalEnemyBegin = 0;

		private ArrayList arGeneral;		//LVClient.Command.CityObj.MilitaryGeneral
		private Hashtable hastGeneral; //	hastGeneral[generalID, LVClient.Command.CityObj.MilitaryGeneral]

		private static ArrayList timeListForTest = new ArrayList();


		/// <summary>
		/// 
		/// </summary>
		/// <param name="battleid"></param>
		/// <param name="sleeptime">Thời gian chờ trước khi vào chiến trường, tính bằng giây</param>
		/// <param name="soluongtuongdanh1dich"></param>
		/// <param name="timedoitranhinh"></param>
		/// <param name="phuongthuctancong"></param>
		/// <param name="phuongthucchonmuctieu"></param>
		/*public AUTOFIGHTING(int battleid, int sleeptime, int soluongtuongdanh1dich, int timedoitranhinh, int phuongthuctancong, int phuongthucchonmuctieu)
		{
			this.Battleid = battleid;
			this.Sleeptime = sleeptime;		//giây
			this.SoTuongDanh1TuongDich = soluongtuongdanh1dich;
			this.TimeDoiTranHinh = timedoitranhinh;
			this.PhuongThucSeTanCong = phuongthuctancong;
			this.PhuongThucChonMucTieu = phuongthucchonmuctieu;
		}
	*/
		
		
		/// <summary>
		/// 
		/// </summary>
		/// <param name="battleid"></param>
		/// <param name="sleeptime">Thời gian chờ trước khi vào chiến trường, tính bằng giây</param>
		/// <param name="soluongtuongdanh1dich"></param>
		/// <param name="general">array LVClient.Command.CityObj.MilitaryGeneral</param>
		public AUTOFIGHTING(int battleid, int sleeptimeInSecond, int soluongtuongdanh1dich, ArrayList general)
		{
			this.Battleid = battleid;
			this.SleeptimeInSecond = sleeptimeInSecond;		//giây
			this.SoTuongDanh1TuongDich = soluongtuongdanh1dich;
			this.arGeneral = general;

			hastGeneral = new Hashtable();

			for(int i=0; i< general.Count; i++)
			{
				LVClient.Command.CityObj.MilitaryGeneral g = (LVClient.Command.CityObj.MilitaryGeneral)general[i];
                try
                {
                    hastGeneral.Add(g.GeneralId, g);
                }
                catch (Exception ex) { }
			}
            
		}

		public override void run()
		{
			try
			{
				int sleep = SleeptimeInSecond;	// giây
				LVClient.Command.OPTObj.BattleField battle = null;

				sleep = sleep - 5 * 60;	// ngủ đến trước khi vào trận 5p
				if (sleep > 0)
				{

					timeListForTest.Add(Battleid + "_" + DateTime.Now.AddSeconds(sleep).ToString("dd-mm hh:mm:ss") + "_ Sleep " + sleep + "s");
					Thread.Sleep(sleep * 1000);
				}
				if (BattleIDRunning.Contains(Battleid)) return ;

				int count = 0;
				do
				{
					try
					{
						battle = Command.OPT.GetBattleField(Battleid);
					}
					catch (Exception ex)
					{
						battle = null;
					}

					if (battle != null)
					{
						GoBattle(battle);  						
						break;
					}
					Thread.Sleep(5 * 1000);	// ngủ 5s
					count++;
				} while (battle == null && count < 80);
			}
			catch (Exception ex)
			{
			}
			finally
			{
                try
                {
                    if (timeListForTest.Count != 0) timeListForTest.RemoveAt(0);

                    for (int i = 0; i < BattleIDList.Count; i++)
                    {
                        if (int.Parse(BattleIDList[i].ToString()) == Battleid)
                            BattleIDList.RemoveAt(i);
                    }
                }
                catch (Exception ex) { }


               // if (BattleIDList.Count !=0) BattleIDList.Remove(Battleid);
			}  			
		}

		private void GoBattle(LVClient.Command.OPTObj.BattleField battle)
		{
            try
            {
                //int timeDoiTranHinh = this.TimeDoiTranHinh;   //10;	   //  đổi trận hình ở 10s cuối
                int sleep;
                BattleIDRunning.Add(Battleid);
                while (true)
                {
                    if (TotalEnemyBegin < battle.enemytroops.Length) TotalEnemyBegin = battle.enemytroops.Length;
                    //if (battle.Timeleft < timeDoiTranHinh) ChonMucTieuNDoiTranHinh(battle);

                    ChonMucTieuNDoiTranHinh(battle);

                    sleep = (int)(battle.Timeleft / 3);
                    if (sleep > 15) Thread.Sleep(sleep * 1000);	// ngu 1s


                    int count = 0;
                    do
                    {
                        battle = Command.OPT.GetBattleField(Battleid);
                        if (battle == null) Thread.Sleep(3 * 1000);
                        count++;
                    } while (battle == null && count < 30);

                    if (battle == null) break;		  // lỗi, không đọc được


                } //end while (true)
            }
            catch (Exception ex)
            {
            }

            finally
            {
                try
                {
                   // if (BattleIDRunning.Count != 0) BattleIDRunning.Remove(Battleid);
                    
                    for (int i = 0; i < BattleIDRunning.Count; i++)
                    {
                        if (int.Parse(BattleIDRunning[i].ToString()) == Battleid)
                            BattleIDRunning.RemoveAt(i);
                    }
                }
                catch (Exception ex) { }
            }	

		}

		private void ChonMucTieuNDoiTranHinh(LVClient.Command.OPTObj.BattleField battle)
		{
			try
			{
				//if (battle.SoTuongDanh1TuongDich == 0) return;		//tuy chon muc tieu

				//if (this.SoTuongDanh1TuongDich == 0
				//			&& this.PhuongThucTanCong == Common.WarFunc.PHUONGTHUCTANCONG.TuyChon) return;

				
				Command.OPTObj.GeneralInCombat[] mytroops = battle.mytroops;
				Command.OPTObj.GeneralInCombat[] enemytroops = battle.enemytroops;

			
				//Array.Sort(mytroops);				// sắp xếp theo số lượng quân giảm dần
				SortTarget(mytroops, PHUONGTHUCCHONMUCTIEU.QuanDongNhat);

				// Sắp xếp lại quân địch
				//SortTarget(enemytroops, PhuongThucChonMucTieu);

				int countmytroops = 0;			// mytroops.Length - 1;

				int countenemytroops = 0;		// enemytroops.Length - 1;
				//int countenemytroops = 0;

				int phuongthuctancong;
				int tranhinh;
				

				LVClient.Command.CityObj.MilitaryGeneral generalPara = null;
				while (true)
				{
					int lastPhuongThucChonMucTieu = 0;

					//if (countmytroops < 0) break;
					if (countmytroops >= mytroops.Length) break;

					//if (countenemytroops < 0) countenemytroops = enemytroops.Length - 1;
					if (countenemytroops >= enemytroops.Length) countenemytroops = 0;

		

					int i = 0;
					do
					{
						// kiểm tra xem tướng có trong list ko
						if (hastGeneral.Contains(0))
						{
							generalPara = (LVClient.Command.CityObj.MilitaryGeneral)hastGeneral[0];
						}
						else
						{
							if (!hastGeneral.Contains(mytroops[countmytroops].GeneralId))
							{
								countmytroops++;
								i++;
								if (countmytroops >= mytroops.Length) return;
								continue;
							}
							else
							{
								generalPara = (LVClient.Command.CityObj.MilitaryGeneral)hastGeneral[mytroops[countmytroops].GeneralId];
							}
						}

						if (lastPhuongThucChonMucTieu != generalPara.PhuongThucChonMucTieuID)
						{
							// Sắp xếp lại quân địch
							SortTarget(enemytroops, generalPara.PhuongThucChonMucTieuID);
							lastPhuongThucChonMucTieu = generalPara.PhuongThucChonMucTieuID;
						}


                        //nếu quân địch đã bị hỗn loạn thì không đánh nữa, chon thang khac
                        if (enemytroops[countenemytroops].Military.TrangThaiQuanDoi == LVClient.Command.CityObj.MilitaryGeneral.TrangThaiQuanDoi.HonLoan)
                        {
                            bool allHonloan = true;
                            for (int k = 0; k < enemytroops.Length; k++)
                                if (enemytroops[k].Military.TrangThaiQuanDoi != LVClient.Command.CityObj.MilitaryGeneral.TrangThaiQuanDoi.HonLoan)
                                {
                                    allHonloan = false;
                                    break;
                                }

                            if (!allHonloan)
                            {
                                countenemytroops++;
                                if (countenemytroops >= enemytroops.Length) countenemytroops = 0;
                                continue;
                            }

                            /*
                            if (countenemytroops < enemytroops.Length - 1 &&
                                enemytroops[countenemytroops + 1].Military.TrangThaiQuanDoi
                                != LVClient.Command.CityObj.MilitaryGeneral.TrangThaiQuanDoi.HonLoan)
                            {
                                countenemytroops++;
                            }
                            else
                                if (countenemytroops > 0 &&
                                    enemytroops[countenemytroops - 1].Military.TrangThaiQuanDoi
                                        != LVClient.Command.CityObj.MilitaryGeneral.TrangThaiQuanDoi.HonLoan)
                                {

                                    countenemytroops--;
                                }
                             */
                        }



						//phuongthuctancong = mytroops[countmytroops].PhuongThucTanCongID;
						phuongthuctancong = generalPara.PhuongThucTanCongID;

						if (phuongthuctancong == Common.WarFunc.PHUONGTHUCTANCONG.PhanKich)
						{
							// nếu địch chỉ còn 1/3 hoặc 3 thì sẽ tấn công tùy chọn
							if (battle.enemytroops.Length < (this.TotalEnemyBegin / 3) || battle.enemytroops.Length <=3)
							{
								phuongthuctancong = Common.WarFunc.PHUONGTHUCTANCONG.TuyChon;
							}
						}
						else
						{
							if (phuongthuctancong == Common.WarFunc.PHUONGTHUCTANCONG.TuyChon)
								phuongthuctancong = mytroops[countmytroops].PhuongThucDangTanCong;
						}
					

//						if ((this.SoTuongDanh1TuongDich !=0 || this.PhuongThucSeTanCong != 0 )&&  
//								(phuongthuctancong != mytroops[countmytroops].PhuongThucDangTanCong
//								|| mytroops[countmytroops].TagetID != enemytroops[countenemytroops].attackid))

                        


						if ((phuongthuctancong != mytroops[countmytroops].PhuongThucDangTanCong
								|| mytroops[countmytroops].TagetID != enemytroops[countenemytroops].attackid))
						{
							Command.OPT.ChangeTargetAttack(phuongthuctancong, battle.Battleid,
										mytroops[countmytroops].attackid, enemytroops[countenemytroops].attackid);
							
							mytroops[countmytroops].TagetID = enemytroops[countenemytroops].attackid;													
						}




						// doi tran hinh						
						if (mytroops[countmytroops].TagetID == 0)
							tranhinh = mytroops[countmytroops].Military.TranHinh;		// không có mục tiêu sẽ không đổi trận hình
						else
							tranhinh = enemytroops[countenemytroops].Military.TranHinhKhac;
							//tranhinh = LVClient.Common.WarFunc.GetTranHinhKhac(enemytroops[countenemytroops].Military.TranHinh);
							//tranhinh = myTranHinhID;

						if (battle.Timeleft < generalPara.TimeDoiTranHinhMinutes) 
							if (tranhinh != mytroops[countmytroops].Military.TranHinh)
								if (mytroops[countmytroops].Military.RatioAttack + mytroops[countmytroops].Military.RatioPK + mytroops[countmytroops].Military.RatioStratagem == 100)
									Command.OPT.ChangeGeneralMilitaryAttribute(mytroops[countmytroops], tranhinh);
							
						
						// sử dụng mưu kế
						if (generalPara.MuuKeTrongChienTranID != LVClient.Common.WarFunc.MUUKETRONGCHIENTRUONG.KhongDung)
						{
							LVClient.Command.OPT.DungMuuKeTrongChienTruong(
								battle.Battleid, 
								mytroops[countmytroops].attackid,
								generalPara.MuuKeTrongChienTranID); 
						}
							


						//countmytroops--;
						countmytroops++;
						//if (countmytroops < 0) break;
						if (countmytroops >= mytroops.Length) break;

					
						i++;
					} while (i < this.SoTuongDanh1TuongDich);
					
					
					//countenemytroops--;		
					countenemytroops++;		
				} // end while true
			}
			catch (Exception ex)
			{
			}
		}

		public  void SortTarget(Command.OPTObj.GeneralInCombat[] enemytroop, int phuongthucchonmuctieu)
		{
			switch (phuongthucchonmuctieu)
			{

				case PHUONGTHUCCHONMUCTIEU.QuanDongNhat: 
					SortTargetByQuanDongNhat(enemytroop);
					break;

				case PHUONGTHUCCHONMUCTIEU.TranHinhHieuQua:
					SortTargetByTranHinhHieuQua(enemytroop);
					break;

				case PHUONGTHUCCHONMUCTIEU.TranHinhNQuanDongNhat:
					SortTargetByTranHinhNQuanDongNhat(enemytroop);
					break;


			}

		}

		private void SortTargetByTranHinhHieuQua(Command.OPTObj.GeneralInCombat[] enemytroop)
		{
			int tranhinhquanta = TimTranHinhTotNhat(enemytroop);
			SortTargetByTranHinhYeu(tranhinhquanta, enemytroop);

		}
		private void SortTargetByTranHinhNQuanDongNhat(Command.OPTObj.GeneralInCombat[] enemytroop)
		{
			TimTranHinhTotNhat(enemytroop);
			SortTargetByQuanDongNhat(enemytroop);


		}


		/// <summary>
		/// Sắp xếp mục tiêu theo trận hình, quân địch có trận hình khắc quân ta thì đứng trước (quân ta 0.8), 
		/// mục đích quân ta oánh thằng bị khắc trước
		/// </summary>
		/// <param name="tranhinhquanta"></param>
		/// <param name="enemytroop"></param>
		public static void SortTargetByTranHinhYeu(int tranhinhquanta, Command.OPTObj.GeneralInCombat[] enemytroop)
		{
			double vi, vj;

			Command.OPTObj.GeneralInCombat temp;
			for (int i = 0; i < enemytroop.Length; i++)
				for (int j = i + 1; j < enemytroop.Length; j++)
				{
					vi = enemytroop[i].Military.SyKhi * enemytroop[i].Military.SoQuanDangCo 
							* Command.CityObj.General.GetHeSoTrangThaiQuanDoi(enemytroop[i].Military.TrangThaiQuanDoi);
					vj= enemytroop[j].Military.SyKhi * enemytroop[j].Military.SoQuanDangCo
						* Command.CityObj.General.GetHeSoTrangThaiQuanDoi(enemytroop[j].Military.TrangThaiQuanDoi);
					
					if (
							(
								LVClient.Common.WarFunc.ArrayValue[tranhinhquanta, enemytroop[i].Military.TranHinh] >
									LVClient.Common.WarFunc.ArrayValue[tranhinhquanta, enemytroop[j].Military.TranHinh]
								&& vi  * 0.85 < vj
									
							)
						||
							(
								vi  < vj * 0.85
							)
						)
					{

						temp = enemytroop[i];
						enemytroop[i] = enemytroop[j];
						enemytroop[j] = temp;
					}
				}

		}


		/// <summary>
		/// Sắp xếp mục tiêu theo số lượng quân địch giảm dần (tính theo số quân, sỹ khí và trạng thái quân đội)
		/// </summary>
		/// <param name="enemytroop">Command.OPTObj.GeneralInCombat[]: arr mục tiêu sẽ được sắp xếp lại </param>
		private static void SortTargetByQuanDongNhat(Command.OPTObj.GeneralInCombat[] enemytroop)
		{		
			
			Command.OPTObj.GeneralInCombat temp;
			double vi, vj;
			for (int i=0; i < enemytroop.Length; i++)
				for (int j = i + 1; j < enemytroop.Length; j++)
				{
					vi = enemytroop[i].Military.SoQuanDangCo * enemytroop[i].Military.SyKhi * Command.CityObj.General.GetHeSoTrangThaiQuanDoi(enemytroop[i].Military.TrangThaiQuanDoi);
					vj = enemytroop[j].Military.SoQuanDangCo * enemytroop[j].Military.SyKhi * Command.CityObj.General.GetHeSoTrangThaiQuanDoi(enemytroop[j].Military.TrangThaiQuanDoi);
					if ( vi < vj ||
						(
							vi == vj  &&
							enemytroop[i].Military.KyBinh[0] + enemytroop[i].Military.CungThu[0] < enemytroop[j].Military.KyBinh[0] + enemytroop[j].Military.CungThu[0]
						)
						)
					{
						temp = enemytroop[i];
						enemytroop[i] = enemytroop[j];
						enemytroop[j] = temp;
					}
				}
		
			
		}

		/// <summary>
		/// Tìm trận hình tốt nhất (phụ thuộc vào: hệ số trận hình, quân số, sy khi, hệ số trạng thái quân đội)
		/// </summary>
		/// <param name="genArr">Array target mục tiêu (quân địch)</param>
		/// /// <returns>int: trận hình tốt nhất (đối kháng với enemytroop[])</returns>
		private static int TimTranHinhTotNhat(Command.OPTObj.GeneralInCombat[] enemytroop)
		{
			double[,] arrValue = new double[LVClient.Common.WarFunc.TRANHINHAMOUNT, LVClient.Common.WarFunc.TRANHINHAMOUNT]; 

			// value = hệ số trận hình * quân số * sy khi
			/*
			for (int i = 0; i < LVClient.Common.WarFunc.TRANHINHAMOUNT; i++)
			{
				for (int j = 0; j < enemytroop.Length; j++)
				{

					arrValue[i, enemytroop[j].Military.TranHinh]
						+= LVClient.Common.WarFunc.ArrayValue[i, enemytroop[j].Military.TranHinh] * enemytroop[j].Military.SoQuanDangCo
						* enemytroop[j].Military.SyKhi  
						* Command.CityObj.General.GetHeSoTrangThaiQuanDoi(enemytroop[j].Military.TrangThaiQuanDoi); ;
				}
			}// end 			for (int i = 1; i < LVClient.Common.WarFunc.TRANHINHAMOUNT; i++)
			*/

			// value = hệ số trận hình * quân số * sy khi * trạng thái quân đội
			double tmp;
			for (int enemyidx = 0; enemyidx < enemytroop.Length; enemyidx++)
			{
				tmp = enemytroop[enemyidx].Military.SoQuanDangCo * enemytroop[enemyidx].Military.SyKhi
							* Command.CityObj.General.GetHeSoTrangThaiQuanDoi(enemytroop[enemyidx].Military.TrangThaiQuanDoi);
				
				for (int i = 0; i < LVClient.Common.WarFunc.TRANHINHAMOUNT; i++)
				{
					arrValue[i, enemytroop[enemyidx].Military.TranHinh]
						+= LVClient.Common.WarFunc.ArrayValue[i, enemytroop[enemyidx].Military.TranHinh] * tmp;
				}
			}// end 			for (int i = 1; i < LVClient.Common.WarFunc.TRANHINHAMOUNT; i++)

			
			double[] arrTongTheoChieuNgang = new double[LVClient.Common.WarFunc.TRANHINHAMOUNT];
			double[] arrTongTheoChieuDoc = new double[LVClient.Common.WarFunc.TRANHINHAMOUNT]; 
		
			// tổng 1 trận hình
			for (int i = 0; i < LVClient.Common.WarFunc.TRANHINHAMOUNT; i++)
			{
				for (int j = 0; j < LVClient.Common.WarFunc.TRANHINHAMOUNT; j++)
				{
					arrTongTheoChieuNgang[i] += arrValue[i,j];
					arrTongTheoChieuDoc[i] += arrValue[j, i];
				}
			}

			// sắp xếp lại
			// tranhinh quân ta hiệu quả nhất là tranhinhquanta[0], kém hiệu quả nhất là tranhinh[5]
			int[] tranhinhquanta = new int[] { 0, 1, 2, 3, 4, 5 };
			
			// traanj hinh dich[0] can danh dau tien 
			int[] tranhinhquandich = new int[] { 0, 1, 2, 3, 4, 5 };
			double temp1;
			int temp2;
			for (int i=0; i < LVClient.Common.WarFunc.TRANHINHAMOUNT; i++)
				for (int j=i+1; j < LVClient.Common.WarFunc.TRANHINHAMOUNT; j++)
			{
				if (arrTongTheoChieuNgang[i] < arrTongTheoChieuNgang[j])
				{
					temp1 = arrTongTheoChieuNgang[i];
					arrTongTheoChieuNgang[i] = arrTongTheoChieuNgang[j];
					arrTongTheoChieuNgang[j] = temp1;

					temp2 = tranhinhquanta[i];
					tranhinhquanta[i] = tranhinhquanta[j];
					tranhinhquanta[j] = temp2;

				}

				if (arrTongTheoChieuDoc[i] < arrTongTheoChieuDoc[j])
				{					

					temp2 = tranhinhquandich[i];
					tranhinhquandich[i] = tranhinhquandich[j];
					tranhinhquandich[j] = temp2;

				}
			}

			// đưa vào Hastable [tranhinh, vịtrí], vị trí 0 là hiệu quả nhất
			/*Hashtable hasTempQuaTa = new Hashtable();
			Hashtable hasTempQuaDich = new Hashtable();
			for (int i = 0; i < tranhinhquanta.Length; i++)
			{
				hasTempQuaTa.Add(tranhinhquanta[i], i);
			}
			for (int i = 0; i < tranhinhquandich.Length; i++)
			{
				hasTempQuaDich.Add(tranhinhquandich[i], i);
			}
			*/

			// lưu trận hình tốt nhất của quân ta vào arr quân địch để lúc cần có thể lấy ra
			for (int i = 0; i < enemytroop.Length; i++)
			{
				enemytroop[i].Military.TranHinhKhac = tranhinhquanta[0];
			}


			return tranhinhquanta[0];
		}

		/// <summary>
		/// Auto battle
		/// </summary>
		/// <param name="battleid"></param>
		/// <param name="sleeptime">Thời gian chờ đến khi vào chiến trường (giây)</param>
		/// <param name="soluongtuongdanh1dich"></param>
		/// <param name="timedoitranhinh">Tính bằng giây</param>
		/// <param name="phuongthuctancong"></param>
		/// <returns></returns>
		/*public static AUTOFIGHTING startBattle(int battleid, int sleeptime, int soluongtuongdanh1dich, int timedoitranhinh, int phuongthuctancong, int phuongthucchonmuctieu)
		{
			//LVClient.Command.OPTObj.BattleField battle = Command.OPT.GetBattleField(battleid);
			if (sleeptime > 0)
			{
				if (BattleIDList.Contains(battleid)) return null;
			}
			else
			{
				if (BattleIDRunning.Contains(battleid)) return null;
			}


			if (!BattleIDList.Contains(battleid))  BattleIDList.Add(battleid);
			AUTOFIGHTING btf = new AUTOFIGHTING(battleid, sleeptime, soluongtuongdanh1dich, timedoitranhinh, phuongthuctancong, phuongthucchonmuctieu);
			
			btf.InThread = new Thread(new ThreadStart(btf.run));
			btf.IsRun = true;
			btf.InThread.Start();
			return btf;
		}
		*/


        /// <summary>
        /// Auto battle
        /// </summary>
        /// <param name="battleid"></param>
        /// <param name="sleeptime">Thời gian chờ đến khi vào chiến trường (giây)</param>
        /// <param name="soluongtuongdanh1dich"></param>
        /// <param name="general">LVClient.Command.CityObj.MilitaryGeneral</param>
        /// <returns></returns>
        public static AUTOFIGHTING startBattle(int battleid, int sleeptime, int soluongtuongdanh1dich, LVClient.Command.CityObj.MilitaryGeneral general)
        {

            ArrayList g = new ArrayList();
            g.Add(general);
            return startBattle(battleid, sleeptime, soluongtuongdanh1dich, g);
        }


		/// <summary>
		/// Auto battle
		/// </summary>
		/// <param name="battleid"></param>
		/// <param name="sleeptime">Thời gian chờ đến khi vào chiến trường (giây)</param>
		/// <param name="soluongtuongdanh1dich"></param>
		/// <param name="general">list MilitaryGeneral</param>
		/// <returns></returns>
		public static AUTOFIGHTING startBattle(int battleid, int sleeptime, int soluongtuongdanh1dich, ArrayList general)
		{
			//LVClient.Command.OPTObj.BattleField battle = Command.OPT.GetBattleField(battleid);
			if (sleeptime > 30)
			{
				// Đếm xem có bao nhiêu thằng đang chờ
				int count = 0;
				for (int i = 0; i < BattleIDList.Count; i++)
				{
					if (battleid == int.Parse(BattleIDList[i].ToString()))
						count++;
				}
				if (count > 30)				// chir cho toois da 30 thang cho
					return null;
					//if (BattleIDList.Contains(battleid)) return null;
			}
			else
			{
				if (BattleIDRunning.Contains(battleid)) return null;
			}

			
			//if (!BattleIDList.Contains(battleid)) BattleIDList.Add(battleid);
			BattleIDList.Add(battleid);
			
			
			//AUTOFIGHTING btf = new AUTOFIGHTING(battleid, sleeptime, soluongtuongdanh1dich, timedoitranhinh, phuongthuctancong, phuongthucchonmuctieu);
			AUTOFIGHTING btf = new AUTOFIGHTING(battleid, sleeptime, soluongtuongdanh1dich, general);


			btf.InThread = new Thread(new ThreadStart(btf.run));
			btf.IsRun = true;
			btf.InThread.Start();
			return btf;
		}


		public class PHUONGTHUCCHONMUCTIEU
		{

			public const int TuyChon = 0;			//
			public const int QuanDongNhat = 1;			// Phang quân đông nhất
			public const int TranHinhHieuQua = 2;	 // Trận hình hiệu quả, phang quân mình bị khắc (mình đánh trước)
			public const int TranHinhNQuanDongNhat = 3;	//Trận hình hiệu quả, đánh quân đông nhất

		}

	
		
	}

	
}



/*

[["Hủy bỏ trạng thái"],[
 "Sử dụng đối với quân đội mình trong chiến trường, sau khi sử dụng quân đội lập tức giải trừ trạng thái, khôi phục lại bình thường."],[1],[96],[5],[6]],
    [["Kim thiền thoát xác"],[
 "Sử dụng đối với quân đội của mình trong chiến trường. Sau khi sử dụng quân đội sẽ trực tiếp rút khỏi chiến đấu, sĩ khí không bị tổn thất."],[1],[92],[10],[10]],
    [["Phản khách vi chủ"],[
 "Sử dụng đối với quân đội của mình trong chiến trường. Sau khi sử dụng quân đội sẽ được ưu tiên công kích trong hiệp kế tiếp."],[1],[93],[10],[10]],
    [["Cầm tặc cầm vương"],["Sử dụng đối với quân đội của mình trong chiến trường, 
 * sau khi sử dụng nếu quân đội chiến thắng trong hiệp kế tiếp thì phe địch sẽ giảm một nửa sĩ khí."],[1],[95],[10],[10]],
    [["Quan môn tróc tặc"],["Sử dụng đối với phe địch trong chiến trường, 
 * sau khi sử dụng quân đội đó sẽ không thể chấp hành lệnh rút quân trong 3 hiệp liên tiếp (
 * trừ phi đối phương sử dụng Kim thiền thoát xác)."],[3],[94],[15],[15]]
    ]

[["Hủy bỏ trạng thái"],["Sử dụng đối với quân đội mình trong chiến trường, sau khi sử dụng quân đội lập tức giải trừ trạng thái, khôi phục lại bình thường."],[1],[96],[5],[6]],
    [["Kim thiền thoát xác"],["Sử dụng đối với quân đội của mình trong chiến trường. Sau khi sử dụng quân đội sẽ trực tiếp rút khỏi chiến đấu, sĩ khí không bị tổn thất."],[1],[92],[10],[10]],
    [["Phản khách vi chủ"],["Sử dụng đối với quân đội của mình trong chiến trường. Sau khi sử dụng quân đội sẽ được ưu tiên công kích trong hiệp kế tiếp."],[1],[93],[10],[10]],
    [["Cầm tặc cầm vương"],["Sử dụng đối với quân đội của mình trong chiến trường, sau khi sử dụng nếu quân đội chiến thắng trong hiệp kế tiếp thì phe địch sẽ giảm một nửa sĩ khí."],[1],[95],[10],[10]],
    [["Quan môn tróc tặc"],["Sử dụng đối với phe địch trong chiến trường, sau khi sử dụng quân đội đó sẽ không thể chấp hành lệnh rút quân trong 3 hiệp liên tiếp (trừ phi đối phương sử dụng Kim thiền thoát xác)."],[3],[94],[15],[15]]

92. Kim thiền thoát xác
93. Phản khách vi chủ
95. Cầm tặc cầm vương

phản khách
http://s3.linhvuong.zooz.vn/GateWay/OPT.ashx?id=70&0.620438009616514&lBattleID=0&lDestPosID=1&lPlusFunc=93

lBattleID	0
lDestPosID	1
lPlusFunc	93

cầm tặc
http://s3.linhvuong.zooz.vn/GateWay/OPT.ashx?id=70&0.19187122354749897&lBattleID=0&lDestPosID=11&lPlusFunc=95

Hủy bỏ trạng thái
http://s3.linhvuong.zooz.vn/GateWay/OPT.ashx?id=70&0.8909512387415796&lBattleID=0&lDestPosID=1&lPlusFunc=96




Sấn hỏa đã kiếp
Sử dụng khi xuất binh, sau khi sử dụng lượng tài nguyên mà quân đội chiến đấu mang về x3.

lBout	-1
lDestX	310
lDestY	-261
lGeneralID1	469089
lGeneralID2	0
lGeneralID3	0
lPlusDestX	0
lPlusDextY	0
lPlusFuncID	78
lTarget1GID	0
lTarget2GID	0
lTarget3GID	0
lType	1
strDestName	Quân đội Uy quốc
tid	0




*/