using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Text;
using System.Windows.Forms;

namespace LVClient.Control {
    public partial class Attack : UserControl {
        public int battleid = 0;
        public Attack() {
            InitializeComponent();
        }

        private void cboMyGeneral_SelectedIndexChanged(object sender, EventArgs e) {
            try {
				Command.OPT.ChangeTargetAttack(1, battleid, ((Command.OPTObj.GeneralInCombat)cboMyGeneral.SelectedValue).attackid, ((Command.OPTObj.GeneralInCombat)cboEnemyGeneral.SelectedValue).attackid);
            } catch (Exception ex) {

            }
        }

        private void cboEnemyGeneral_SelectedIndexChanged(object sender, EventArgs e) {
            try {
				Command.OPT.ChangeTargetAttack(1, battleid, ((Command.OPTObj.GeneralInCombat)cboMyGeneral.SelectedValue).attackid, ((Command.OPTObj.GeneralInCombat)cboEnemyGeneral.SelectedValue).attackid);
            } catch (Exception ex) {

            }
        }
    }
}
