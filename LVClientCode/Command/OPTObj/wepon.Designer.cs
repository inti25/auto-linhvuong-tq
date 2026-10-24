namespace LVClient.Command.OPTObj {
    partial class wepon {
        /// <summary> 
        /// Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary> 
        /// Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing) {
            if (disposing && (components != null)) {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Component Designer generated code

        /// <summary> 
        /// Required method for Designer support - do not modify 
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent() {
            this.lblCityName = new System.Windows.Forms.Label();
            this.cboWepon = new System.Windows.Forms.ComboBox();
            this.cboHorse = new System.Windows.Forms.ComboBox();
            this.cboAmor = new System.Windows.Forms.ComboBox();
            this.cboLevel = new System.Windows.Forms.ComboBox();
            this.txtAmount = new System.Windows.Forms.TextBox();
            this.chkOK = new System.Windows.Forms.CheckBox();
            this.SuspendLayout();
            // 
            // lblCityName
            // 
            this.lblCityName.Location = new System.Drawing.Point(18, 6);
            this.lblCityName.Name = "lblCityName";
            this.lblCityName.Size = new System.Drawing.Size(122, 19);
            this.lblCityName.TabIndex = 0;
            this.lblCityName.Text = "Tên thành";
            // 
            // cboWepon
            // 
            this.cboWepon.FormattingEnabled = true;
            this.cboWepon.Items.AddRange(new object[] {
            "101. Thấu giáp thương",
            "102. Hậu bối đao",
            "103. Hổ bí đao",
            "104. Cổ đồng đao",
            "105. Đại khảm đao",
            "106. Khoan nhận kiếm",
            "107. Tam hoàn đại đao",
            "108. Bách thắng trường đao",
            "201. Thiết thai cung",
            "202. Bá vương nỗ",
            "203. Ly tần cung",
            "204. Bảo điêu cung",
            "205. Ngọc giác cung",
            "206. Trường huyền giáp cung",
            "207. Thần diên cung",
            "208. Phá phong cung"});
            this.cboWepon.Location = new System.Drawing.Point(146, 3);
            this.cboWepon.Name = "cboWepon";
            this.cboWepon.Size = new System.Drawing.Size(81, 21);
            this.cboWepon.TabIndex = 402;
            this.cboWepon.SelectedIndexChanged += new System.EventHandler(this.cboWepon_SelectedIndexChanged);
            // 
            // cboHorse
            // 
            this.cboHorse.FormattingEnabled = true;
            this.cboHorse.Items.AddRange(new object[] {
            "401. Tuyệt địa mã",
            "402. Phiên vũ mã",
            "403. Bôn tiêu mã",
            "404. Dã hành mã",
            "405. Việt ảnh mã",
            "406. Du huy mã",
            "407. Thiết kị mã",
            "408. Xích ký mã",
            "501. Xe ném đá loại nhẹ",
            "511. Xe ném đá loại vừa",
            "521. Xe ném đá loại nặng",
            "531. Xe ném đá hỏa diêm"});
            this.cboHorse.Location = new System.Drawing.Point(233, 3);
            this.cboHorse.Name = "cboHorse";
            this.cboHorse.Size = new System.Drawing.Size(82, 21);
            this.cboHorse.TabIndex = 403;
            // 
            // cboAmor
            // 
            this.cboAmor.FormattingEnabled = true;
            this.cboAmor.Items.AddRange(new object[] {
            "301. Ngư lân giáp",
            "302. Tinh cương giáp",
            "303. Minh quang chiến giáp",
            "304. Địa long chiến giáp",
            "305. Thiên hộ giáp",
            "306. Thảo nghịch khôi giáp",
            "307. Xích nhật chiến giáp",
            "308. Lôi đình chiến giáp"});
            this.cboAmor.Location = new System.Drawing.Point(321, 3);
            this.cboAmor.Name = "cboAmor";
            this.cboAmor.Size = new System.Drawing.Size(77, 21);
            this.cboAmor.TabIndex = 404;
            // 
            // cboLevel
            // 
            this.cboLevel.FormattingEnabled = true;
            this.cboLevel.Items.AddRange(new object[] {
            "1",
            "2",
            "3",
            "4",
            "5"});
            this.cboLevel.Location = new System.Drawing.Point(404, 3);
            this.cboLevel.Name = "cboLevel";
            this.cboLevel.Size = new System.Drawing.Size(43, 21);
            this.cboLevel.TabIndex = 405;
            this.cboLevel.Text = "3";
            // 
            // txtAmount
            // 
            this.txtAmount.Location = new System.Drawing.Point(453, 4);
            this.txtAmount.MaxLength = 10;
            this.txtAmount.Name = "txtAmount";
            this.txtAmount.RightToLeft = System.Windows.Forms.RightToLeft.Yes;
            this.txtAmount.Size = new System.Drawing.Size(78, 20);
            this.txtAmount.TabIndex = 406;
            this.txtAmount.Text = "10000";
            // 
            // chkOK
            // 
            this.chkOK.AutoSize = true;
            this.chkOK.Location = new System.Drawing.Point(3, 6);
            this.chkOK.Name = "chkOK";
            this.chkOK.Size = new System.Drawing.Size(15, 14);
            this.chkOK.TabIndex = 401;
            this.chkOK.UseVisualStyleBackColor = true;
            // 
            // wepon
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 13F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.Controls.Add(this.chkOK);
            this.Controls.Add(this.txtAmount);
            this.Controls.Add(this.cboLevel);
            this.Controls.Add(this.cboAmor);
            this.Controls.Add(this.cboHorse);
            this.Controls.Add(this.cboWepon);
            this.Controls.Add(this.lblCityName);
            this.Name = "wepon";
            this.Size = new System.Drawing.Size(537, 28);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        public System.Windows.Forms.Label lblCityName;
        public System.Windows.Forms.ComboBox cboWepon;
        public System.Windows.Forms.ComboBox cboHorse;
        public System.Windows.Forms.ComboBox cboAmor;
        public System.Windows.Forms.ComboBox cboLevel;
        public System.Windows.Forms.TextBox txtAmount;
        public System.Windows.Forms.CheckBox chkOK;

    }
}
