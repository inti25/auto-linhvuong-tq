using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Text;
using System.Windows.Forms;

namespace LVClient.Control 
{
    public partial class War : UserControl 
	{
        public Command.OPTObj.BattleField battle = null;
        public War() {
            InitializeComponent();
        }

        private void cmdGoToBattle_Click(object sender, EventArgs e) {
            battle = Command.OPT.GetBattleField(int.Parse(txtId.Text));
            Switch();
        }

        private void cmdForce_Click(object sender, EventArgs e) {
            if (battle != null) {
                foreach (object temp in pnAttack.Controls) {
                    try {
                        Attack attack = (Attack)temp;
						Command.OPTObj.GeneralInCombat my = (Command.OPTObj.GeneralInCombat)attack.cboMyGeneral.SelectedItem;
						Command.OPTObj.GeneralInCombat enemy = (Command.OPTObj.GeneralInCombat)attack.cboEnemyGeneral.SelectedItem;
                        Command.OPT.ChangeBattleArray(my.GeneralId,Common.WarFunc.AntiAttack[enemy.Military.TranHinh]);
                    }catch(Exception ex){
                    }
                }
            }
        }
        public void Switch() {
            if (battle != null) {
                pnAttack.Controls.Clear();
                Attack tempatt = new Attack();
                if (chkIsDefend.Checked) {
                    for (int i = 0; i < battle.alldefendtroops.Length; i++) {
                        tempatt.cboMyGeneral.Items.Add(battle.alldefendtroops[i]);

                    }
                    for (int i = 0; i < battle.allattacktroops.Length; i++) {
                        tempatt.cboEnemyGeneral.Items.Add(battle.allattacktroops[i]);
                    }
                } else {
                    for (int i = 0; i < battle.alldefendtroops.Length; i++) {
                        tempatt.cboEnemyGeneral.Items.Add(battle.alldefendtroops[i]);
                    }
                    for (int i = 0; i < battle.allattacktroops.Length; i++) {
                        tempatt.cboMyGeneral.Items.Add(battle.allattacktroops[i]);
                    }
                }
                tempatt.Dock = DockStyle.Top;
                if (chkIsDefend.Checked) {
                    for (int i = 0; i < battle.alldefendtroops.Length; i++) {
                        Attack tempatt1 = tempatt;
                        pnAttack.Controls.Add(tempatt1);
                    }
                } else {
                    for (int i = 0; i < battle.allattacktroops.Length; i++) {
                        Attack tempatt1 = tempatt;
                        pnAttack.Controls.Add(tempatt1);
                    }
                }
            }
        }
        private void chkIsDefend_CheckedChanged(object sender, EventArgs e) {
            Switch();
        }

		private void groupBox1_Enter(object sender, EventArgs e)
		{

		}
    }
}
