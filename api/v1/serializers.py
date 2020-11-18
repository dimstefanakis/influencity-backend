from rest_framework import serializers
from accounts.models import User
from instructor.models import Coach
from posts.models import Post, PostImage, PostVideo, PlaybackId
from projects.models import Project, Prerequisite, Milestone, Team
from comments.models import CommentImage, Comment
from subscribers.models import Subscriber
from expertisefields.models import ExpertiseField, ExpertiseFieldAvatar
from tiers.models import Tier


class CoachSerializer(serializers.ModelSerializer):
    expertise_field = serializers.StringRelatedField()
    avatar = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()

    @staticmethod
    def get_projects(coach):
        return ProjectSerializer(coach.created_projects.all(), many=True).data

    @staticmethod
    def get_avatar(coach):
        if coach.avatar:
            return coach.avatar.image.url
        return None

    class Meta:
        model = Coach
        fields = ['name', 'avatar', 'bio', 'expertise_field', 'projects']


class SubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscriber
        fields = ['name']


class UserSerializer(serializers.ModelSerializer):
    coach = CoachSerializer()
    subscriber = SubscriberSerializer()

    class Meta:
        model = User
        fields = ['username', 'email', 'is_coach', 'is_subscriber', 'coach', 'subscriber']


class PrerequisiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prerequisite
        fields = ['description']


class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = ['description']


class ProjectSerializer(serializers.ModelSerializer):
    prerequisites = PrerequisiteSerializer(many=True)
    milestones = MilestoneSerializer(many=True)
    difficulty = serializers.SerializerMethodField()

    def get_difficulty(self, obj):
        return obj.get_difficulty_display()

    class Meta:
        model = Project
        fields = ['name', 'description', 'difficulty', 'team_size', 'prerequisites', 'milestones']


class PostImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, post_image):
        if post_image.image:
            return post_image.image.url
        return None

    class Meta:
        model = PostImage
        fields = ['height', 'width', 'image']


class PlaybackSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaybackId
        fields = ['playback_id', 'policy']


class PostVideoSerializer(serializers.ModelSerializer):
    playback_ids = PlaybackSerializer(many=True)

    class Meta:
        model = PostVideo
        fields = ['asset_id', 'playback_ids']


class PostSerializer(serializers.ModelSerializer):
    coach = CoachSerializer()
    linked_project = ProjectSerializer()
    images = PostImageSerializer(many=True)
    videos = PostVideoSerializer(many=True)

    class Meta:
        model = Post
        fields = ['text', 'coach', 'images', 'videos', 'tiers', 'chained_posts', 'id', 'linked_project']

    def get_fields(self):
        fields = super(PostSerializer, self).get_fields()
        fields['chained_posts'] = PostSerializer(many=True)
        return fields


class PostNoChainSerializer(serializers.ModelSerializer):
    linked_project = ProjectSerializer()
    images = PostImageSerializer(many=True)
    videos = PostVideoSerializer(many=True)

    class Meta:
        model = Post
        fields = ['text', 'images', 'videos', 'id', 'linked_project']


class PostCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Post
        fields = ['text', 'images', 'tiers', 'id', 'linked_project']
        read_only_fields = ['id']

    def create(self, validated_data):

        coach = self.context['request'].user.coach

        try:
            images = validated_data.pop('images')
        except KeyError:
            images = []

        try:
            tiers = validated_data.pop('tiers')
        except KeyError:
            tiers = []

        post = Post.objects.create(coach=coach, **validated_data)
        post.images.set(images)
        post.tiers.set(tiers)

        return post


class ChainedPostsSerializer(serializers.Serializer):
    posts = PostNoChainSerializer(many=True)

    def create(self, validated_data):
        coach = self.context['request'].user.coach
        results = {
            'posts': []
        }
        main_post = Post.objects.none()
        posts = validated_data.pop('posts')
        for i, post in enumerate(posts):

            # check if images exist then pop it from validation
            images = []
            try:
                images = post.pop('images')
            except KeyError:
                pass

            new_post = Post.objects.create(coach=coach, **post)

            # assign first post
            if i == 0:
                main_post = new_post
            # then chain the rest to the main post
            else:
                main_post.chained_posts.add(new_post)

            # set previously popped images
            new_post.images.set(images)

            results['posts'].append(new_post)
        return results

    def update(self, instance, validated_data):
        pass


class ChainPostsSerializer(serializers.Serializer):
    post_ids = serializers.JSONField()

    def create(self, validated_data):
        ids = validated_data['post_ids']  #.split(",")

        # convert all string ids to integers
        #ids = list(map(lambda item: int(item), ids))

        # get initial post to chain the rest
        main_post = Post.objects.get(pk=ids[0])

        # for each id chain it to the main_post
        for _id in ids:

            # ignore the first id
            if _id != ids[0]:
                post = Post.objects.get(pk=_id)
                main_post.chained_posts.add(post)

        return {"post_ids": ids}

    def update(self, instance, validated_data):
        pass


class CoachNewPosts(serializers.Serializer):
    coach = serializers.SerializerMethodField()
    new_posts = serializers.SerializerMethodField()

    def get_coach(self, coach):
        return CoachSerializer(coach).data

    def get_new_posts(self, coach):
        return PostSerializer(coach.posts.exclude(parent_post__isnull=False), many=True).data

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    class Meta:
        fields = ['coach', 'new_posts']
        read_only_fields = fields


class NewPostsSerializer(serializers.Serializer):
    posts_per_coach = serializers.SerializerMethodField()

    def get_posts_per_coach(self, coach):
        return CoachNewPosts(coach).data

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    class Meta:
        fields = ['posts_per_coach']
        read_only_fields = fields


class CommentImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, comment_image):
        if comment_image.image:
            return comment_image.image.url
        return None

    class Meta:
        model = CommentImage
        fields = ['height', 'width', 'image']


class CommentSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    images = CommentImageSerializer(many=True)

    class Meta:
        model = Comment
        fields = ['text', 'images', 'user']


class CreateCommentSerializer(serializers.ModelSerializer):
    images = CommentImageSerializer(many=True, required=False)

    def create(self, validated_data):
        user = self.context['request'].user

        try:
            images = validated_data.pop('images')
        except KeyError:
            images = []
        comment = Comment.objects.create(user=user, **validated_data)
        comment.images.set(images)

        return comment

    class Meta:
        model = Comment
        fields = ['text', 'images', 'user', 'post']
        read_only_fields = ['user']


class MyProjectsSerializer(serializers.ModelSerializer):
    prerequisites = PrerequisiteSerializer(many=True)
    difficulty = serializers.SerializerMethodField()
    milestones = serializers.SerializerMethodField()

    def get_milestones(self, project):
        user = self.context['request'].user
        team = user.subscriber.teams.filter(project=project).first()
        _milestones = []
        completed = False
        for milestone in project.milestones.all():
            if team in milestone.completed_teams.all():
                completed = True
            _milestones.append({'description': milestone.description, 'completed': completed})
        return _milestones

    def get_difficulty(self, obj):
        return obj.get_difficulty_display()

    class Meta:
        model = Project
        fields = ['name', 'description', 'difficulty', 'team_size', 'prerequisites', 'milestones']


class TeamSerializer(serializers.ModelSerializer):
    members = SubscriberSerializer(many=True)
    project = serializers.StringRelatedField()
    milestones = serializers.SerializerMethodField()

    def get_milestones(self, team):
        _milestones = []
        completed = False
        for milestone in team.milestones.all():
            if milestone.completed_teams.filter(team=team).exists():
                completed = True
            _milestones.append({'description': milestone.description, 'completed': completed})

    class Meta:
        model = Team
        fields = ['name', 'avatar', 'project', 'members', 'milestones']


class ExpertiseAvatarSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, expertise_avatar):
        if expertise_avatar.image:
            return expertise_avatar.image.url
        return None

    class Meta:
        model = ExpertiseFieldAvatar
        fields = ['width', 'height', 'image']


class ExpertiseSerializer(serializers.ModelSerializer):
    avatar = ExpertiseAvatarSerializer()

    class Meta:
        model = ExpertiseField
        fields = ['name', 'avatar']


class TierSerializer(serializers.ModelSerializer):
    tier_full = serializers.SerializerMethodField()

    def get_tier_full(self, obj):
        return obj.get_tier_display()

    class Meta:
        model = Tier
        fields = ['id', 'tier', 'tier_full', 'label', 'subheading', 'credit']
